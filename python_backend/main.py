import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# 🌱 Nạp biến môi trường từ file .env (nếu có). Hoàn toàn tùy chọn —
# thiếu thư viện python-dotenv thì bỏ qua và chạy y như cũ.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import cv2
import numpy as np
import pymupdf  # Thư viện đọc PDF (PyMuPDF) — dùng tên mới để hết cảnh báo fitz deprecated
import pytesseract
import requests  # Gọi Gemini AI từ backend
import spacy
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 1. MỞ KHÓA CORS CHO TRÌNH DUYỆT GIAO TIẾP
# Mặc định "*" y như trước (chạy local không đổi gì).

# Khi deploy, đặt biến môi trường ALLOWED_ORIGINS cho an toàn, ví dụ:
#   ALLOWED_ORIGINS=https://app-luyen-doc.onrender.com
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. KHỞI ĐỘNG NÃO BỘ NLP (spaCy)
print("⏳ Đang tải mô hình Ngôn ngữ học spaCy...")
nlp = spacy.load("en_core_web_sm")
print("✅ Đã tải xong spaCy!")

# 3. NẠP TỪ ĐIỂN VÀO RAM (Bao gồm cả Cấp độ, Phiên âm và Nghĩa)
TU_DIEN = {}
du_ong_dan = "full-word.json"

if os.path.exists(du_ong_dan):
    with open(du_ong_dan, "r", encoding="utf-8") as file:
        data = json.load(file)
        for item in data:
            val = item.get("value", {})
            word = val.get("word", "")
            level = val.get("level", "")
            type_tu = val.get("type", "")  # Từ loại (noun, verb, adjective...)
            # Phiên âm nằm trong nhánh phonetics (us/uk), không phải cấp cao nhất
            phonetics = val.get("phonetics", {})
            # Bỏ dấu / ở đầu/cuối để hiển thị nhất quán (tooltip tự thêm cặp / / khi vẽ)
            ipa = (phonetics.get("us") or phonetics.get("uk") or "").strip("/")
            # Audio phát âm chuẩn Oxford (dùng khi bấm vào từ)
            audio = val.get("us", {}).get("mp3", "") or val.get("uk", {}).get("mp3", "")
            meaning = val.get("meaning", "Đang cập nhật")
            # Lấy câu ví dụ đầu tiên để tooltip có nội dung ngay
            vi_du_sach = val.get("examples", [])
            example = vi_du_sach[0] if vi_du_sach else ""

            # NẠP TẤT CẢ TỪ (không lọc cấp độ) để /tra-tu trả đủ phiên âm + ví dụ kể cả A1/A2.
            # Cấp độ chuẩn khi hiển thị sẽ ưu tiên bảng CSV (CEFR) ở bước 3.5.
            if word:
                TU_DIEN[word.lower()] = {
                    "level": level,
                    "ipa": ipa,
                    "meaning": meaning,
                    "example": example,
                    "audio": audio,
                    "type": type_tu,
                }
    print(f"✅ Đã nạp thành công {len(TU_DIEN)} từ vựng cốt lõi vào RAM!")
else:
    print(f"⚠️ Lỗi: Không tìm thấy file {du_ong_dan}.")

# 3.5 NẠP BẢNG CẤP ĐỘ CEFR TỪ CSV (9.936 TỪ — PHỦ CẢ A1/A2) ĐỂ THAY CHO CHỮ "CƠ BẢN"
CAP_DO_CSV = {}
# Ưu tiên bản CSV đặt NGAY CẠNH code (python_backend/ENGLISH_CERF_WORDS.csv) để project
# tự chứa khi deploy. Nếu không có thì quay về đường dẫn cũ "../../" — KHÔNG phá vỡ cách chạy hiện tại.
_goc_backend = os.path.dirname(os.path.abspath(__file__))
_cac_duong_csv = [
    os.path.join(_goc_backend, "ENGLISH_CERF_WORDS.csv"),
    os.path.join(_goc_backend, "..", "..", "ENGLISH_CERF_WORDS.csv"),
]
duong_csv = next((p for p in _cac_duong_csv if os.path.exists(p)), _cac_duong_csv[0])

# Thứ tự CEFR từ dễ → khó. CSV có Nhiều từ lặp lại với 2 cấp độ (vd: house = A1 + C1, man = A1 + C1,
# good = A1 + B2, water = A1 + B2...). Phải luôn giữ cấp độ DỄ NHẤT, nếu không từ vựng rất cơ bản
# sẽ bị xếp sai thành C1/C2 và bị tô màu sai trên bài đọc.
THU_TU_CEFR = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}

def cap_do_de_nhat(a, b):
    """Chọn cấp độ DỄ hơn giữa 2 giá trị (A1 < A2 < B1 < B2 < C1 < C2)."""
    if not a:
        return b
    if not b:
        return a
    return a if THU_TU_CEFR.get(a, 9) <= THU_TU_CEFR.get(b, 9) else b

if os.path.exists(duong_csv):
    with open(duong_csv, "r", encoding="utf-8") as file:
        next(file, None)  # Bỏ dòng tiêu đề "headword,CEFR"
        for dong in file:
            dong = dong.strip()
            if not dong:
                continue
            phan = dong.rsplit(",", 1)  # Tách cấp độ nằm ở cuối dòng
            if len(phan) != 2:
                continue
            dau_tu, cap_do = phan[0].strip().lower(), phan[1].strip()
            # Một số dòng có nhiều biến thể viết tách bằng dấu / (vd: a.m./A.M./am/AM)
            for bien_the in dau_tu.split("/"):
                bien_the = bien_the.strip()
                if bien_the:
                    # Giữ cấp độ DỄ NHẤT khi từ lặp lại nhiều lần — từ cơ bản không bị xếp C1/C2
                    CAP_DO_CSV[bien_the] = cap_do_de_nhat(CAP_DO_CSV.get(bien_the), cap_do)
    print(f"✅ Đã nạp {len(CAP_DO_CSV)} cấp độ CEFR từ CSV vào RAM!")
else:
    print(f"⚠️ Không tìm thấy file {duong_csv} — chữ 'Cơ bản' sẽ còn xuất hiện.")


@lru_cache(maxsize=50000)   # 🚀 nhớ kết quả theo từng từ — bài sau mở lại gần như TỨC THÌ
# ⚠️ Từ điển tĩnh (CSV + full-word.json) nạp 1 lần vào RAM lúc khởi động nên kết quả
#    của hàm này KHÔNG BAO GIỜ đổi trong 1 phiên chạy → cache an toàn tuyệt đối.
def cap_do_cuoi_cung(tu: str) -> str:
    """Cấp độ CEFR: ưu tiên bảng CSV (9.936 từ, phủ cả A1/A2, chính xác hơn);
    từ nào CSV không có thì dùng level trong full-word.json."""
    if not tu:
        return ""
    return CAP_DO_CSV.get(tu) or (TU_DIEN.get(tu, {}).get("level") or "")


# 3.6 TỪ LOẠI (POS) — BẢN ĐỒ NHÃN TIẾNG ANH -> TIẾNG VIỆT
# Đủ 17 nhãn có trong full-word.json (noun, verb, adjective, adverb, preposition...)
POS_TV = {
    "noun": "danh từ",
    "verb": "động từ",
    "adjective": "tính từ",
    "adverb": "trạng từ",
    "pronoun": "đại từ",
    "preposition": "giới từ",
    "determiner": "từ hạn định",
    "number": "số từ",
    "conjunction": "liên từ",
    "exclamation": "thán từ",
    "modal verb": "trợ động từ tình thái",
    "ordinal number": "số thứ tự",
    "auxiliary verb": "trợ động từ",
    "indefinite article": "mạo từ không xác định",
    "linking verb": "động từ nối",
    "definite article": "mạo từ xác định",
    "infinitive marker": "tiểu từ nguyên mẫu",
}
# Nhãn spaCy (pos_) -> tiếng Việt — dự phòng cho từ KHÔNG có trong full-word.json
POS_SPACY_TV = {
    "NOUN": "danh từ", "PROPN": "danh từ riêng", "VERB": "động từ",
    "AUX": "trợ động từ", "ADJ": "tính từ", "ADV": "trạng từ",
    "PRON": "đại từ", "DET": "từ hạn định", "ADP": "giới từ",
    "CCONJ": "liên từ", "SCONJ": "liên từ phụ", "CONJ": "liên từ",
    "NUM": "số từ", "PART": "tiểu từ", "INTJ": "thán từ",
    "SYM": "ký hiệu", "X": "từ khác",
}


def pos_tieng_viet(tu: str, type_tu_dien: str = "", nhan_spacy: str = "") -> str:
    """Từ loại tiếng Việt: ưu tiên 'type' có sẵn trong full-word.json (noun, verb...);
    từ không có trong từ điển thì suy ra bằng spaCy (NOUN, VERB...). Không bao giờ lỗi.

    🚀 nhan_spacy: nhãn từ loại (NOUN/VERB...) ĐÃ CÓ SẴN từ lần gọi spaCy duy nhất của cả
    bài (lemmatize_va_pos) — dùng luôn, KHÔNG gọi nlp() lại từng từ nữa (nhanh gấp ~100 lần)."""
    if type_tu_dien:
        return POS_TV.get(type_tu_dien.lower(), type_tu_dien)
    if nhan_spacy:
        return POS_SPACY_TV.get(nhan_spacy, nhan_spacy)
    if not tu:
        return ""
    doc = nlp(tu)
    if len(doc) > 0:
        return POS_SPACY_TV.get(doc[0].pos_, doc[0].pos_)
    return ""


# 3.7 HỌ TỪ (WORD FAMILY) — FILE TĨNH BIÊN SOẠN SẴN, NẠP VÀO RAM ĐỂ TRA SIÊU NHANH
HO_TU = {}
duong_ho_tu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "word-families.json")
if os.path.exists(duong_ho_tu):
    with open(duong_ho_tu, "r", encoding="utf-8") as file:
        HO_TU = json.load(file)
    print(f"✅ Đã nạp {len(HO_TU)} họ từ (word family) vào RAM!")
else:
    print("⚠️ Không tìm thấy word-families.json — mọi từ sẽ trả họ từ rỗng.")

# Danh sách từ đã xác nhận KHÔNG có họ từ (Gemini xem trước, lưu sẵn) —
# gặp từ này thì trả [] NGAY, không bao giờ gọi Gemini nữa (khỏi treo ~7s).
KHONG_CO_HO_TU = set()
duong_khong = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tu-khong-co-ho-tu.json")
if os.path.exists(duong_khong):
    with open(duong_khong, "r", encoding="utf-8") as file:
        KHONG_CO_HO_TU = set(json.load(file))
    print(f"✅ Đã nạp {len(KHONG_CO_HO_TU)} từ không có họ từ (trả [] ngay không gọi Gemini)!")
CACHE_HO_TU = {}

# 3.8 CỤM TỪ / THÀNH NGỮ / QUÁN NGỮ TIẾNG ANH — FILE TĨNH BIÊN SOẠN SẴN (GIỐNG word-families.json)
# Mỗi mục: {p: cụm từ chuẩn, t: loại (cụm động từ/thành ngữ/collocation...), m: nghĩa tiếng Việt}
CUM_TU_TIENG_ANH = []
duong_cum_tu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cum_tu_tieng_anh.json")
if os.path.exists(duong_cum_tu):
    with open(duong_cum_tu, "r", encoding="utf-8") as file:
        CUM_TU_TIENG_ANH = json.load(file)
    # Sắp theo SỐ TỪ GIẢM DẦN: cụm dài khớp trước, cụm ngắn nằm bên trong sẽ không bị đếm trùng
    CUM_TU_TIENG_ANH.sort(key=lambda e: len(e.get("p", "").split()), reverse=True)
    print(f"✅ Đã nạp {len(CUM_TU_TIENG_ANH)} cụm từ/thành ngữ tiếng Anh vào RAM!")
else:
    print("⚠️ Không tìm thấy cum_tu_tieng_anh.json — tính năng Cụm từ tiếng Anh tạm tắt.")


def lemmatize_danh_sach(cac_tu: list[str]) -> list[str]:
    """Gọt gốc từ (lemma) cho TỪNG từ trong danh sách một cách AN TOÀN.

    ⚠️ KHÔNG nối hết rồi khớp theo VỊ TRÍ token như code cũ — vì từ có dấu nháy đơn
    (vd "it's", "world's") hoặc gạch nối (vd "built-in") bị spaCy tách thành NHIỀU token
    ("it" + "'s", "built" + "-" + "in") làm MỌI TỪ PHÍA SAU lệch cục: temperature nhận
    nhầm lemma "habitation" (bị tô C2 sai + hiện nghĩa "chỗ ở"), difference nhận "cosmic".

    Cách mới: nối các từ bằng dấu cách, rồi khớp từng từ theo KHOẢNG KÝ TỰ của chính nó
    (offset trong chuỗi đã nối) — tuyệt đối không bao giờ lệch, kể cả khi một từ tách
    thành nhiều token."""
    if not cac_tu:
        return []
    doc = nlp(" ".join(cac_tu))
    # Offset (vị trí ký tự) bắt đầu của từng từ trong chuỗi đã nối (mỗi từ cách 1 dấu cách)
    bat_dau = []
    vi_tri = 0
    for w in cac_tu:
        bat_dau.append(vi_tri)
        vi_tri += len(w) + 1
    cac_goc = []
    for i, w in enumerate(cac_tu):
        ket = bat_dau[i] + len(w)  # ký tự ngay sau từ thứ i (trong chuỗi đã nối)
        goc = w
        for t in doc:
            if bat_dau[i] <= t.idx < ket:
                # Bỏ qua dấu câu/dấu cách — lấy lemma của token chữ đầu tiên thuộc phạm vi từ này
                if not t.is_punct and not t.is_space:
                    goc = t.lemma_.lower()
                    break
        cac_goc.append(goc)
    return cac_goc


# Các gốc ĐÚNG LÀ trợ động từ thật — chỉ những từ này mới hiện "trợ động từ" trong tooltip.
TRO_DONG_TU_GOC = {
    "be", "am", "is", "are", "was", "were", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
}


def lemmatize_va_pos(cac_tu: list[str]):
    """Gốt gốc từ + LẤY LUÔN nhãn từ loại bằng ĐÚNG 1 LẦN gọi spaCy cho cả danh sách.

    Trả về (danh sách gốc từ, {gốc từ: nhãn spaCy như 'NOUN'/'VERB'}).

    🐞 VÌ SAO CẦN HÀM NÀY: trước đây /lay-cap-do gọi pos_tieng_viet() cho TỪNG từ, mà
    từ nào không có trong full-word.json lại chạy nlp(từ) riêng → bài 300 từ = 300 lần
    spaCy ≈ 10 GIÂY > 7 giây trình duyệt chờ → bị ngắt → BẢNG CẤP ĐỘ TRỐNG → không tô màu.
    Nay chỉ 1 lần spaCy cho cả bài, phần còn lại là tra từ điển trong RAM.
    """
    if not cac_tu:
        return [], {}
    doc = nlp(" ".join(cac_tu))
    bat_dau = []
    vi_tri = 0
    for w in cac_tu:
        bat_dau.append(vi_tri)
        vi_tri += len(w) + 1
    cac_goc = []
    nhan_pos = {}
    for i, w in enumerate(cac_tu):
        ket = bat_dau[i] + len(w)
        goc = w
        for t in doc:
            if bat_dau[i] <= t.idx < ket:
                if not t.is_punct and not t.is_space:
                    goc = t.lemma_.lower()
                    nhan = t.pos_
                    # ⚠️ spaCy gắn nhãn AUX cho CẢ động từ chính ở dạng quá khứ phân từ /
                    # gerund (leavened, building...) khi nằm trong câu bị động.
                    # → Chỉ những gốc ĐÚNG LÀ trợ động từ thật (be/have/do/will/can/must...)
                    #   mới giữ "trợ động từ"; còn lại trả về "động từ" cho đúng.
                    if nhan == "AUX" and goc not in TRO_DONG_TU_GOC:
                        nhan = "VERB"
                    nhan_pos[goc] = nhan
                    break
        cac_goc.append(goc)
    return cac_goc, nhan_pos

# 3.6 BỘ NHỚ ĐỆM + DỊCH GOOGLE DÙNG CHUNG (GIẢM TẢI MẠNG CỰC MẠNH)
PHIEN_DICH = requests.Session()  # phiên kết nối dùng chung (keep-alive -> dịch nhanh hơn nhiều)
CACHE_DICH = {}     # cache nghĩa Google theo từ
CACHE_NGHIA = {}    # cache kết quả /nghia/{word}
CACHE_TRA_TU = {}   # cache toàn bộ kết quả /tra-tu
CACHE_AI = {}       # cache kết quả Gemini theo (từ, mode)

def dich_mymemory(tu: str) -> str:
    """Dự phòng khi Google dịch lỗi (429/bị chặn/treo mạng): dùng MyMemory — miễn phí, không cần API key.
    CHỈ trả về kết quả KHÔNG rỗng — lần sau vẫn thử Google trước."""
    if not tu:
        return ""
    try:
        r = PHIEN_DICH.get(
            "https://api.mymemory.translated.net/get",
            params={"q": tu, "langpair": "en|vi"},
            timeout=6,
        )
        if r.ok:
            du_lieu = r.json()
            nghia = (du_lieu.get("responseData") or {}).get("translatedText") or ""
            # MyMemory đôi khi trả về đúng nguyên từ tiếng Anh (không phải bản dịch) -> coi như không dịch được
            if nghia.strip().lower() == tu.strip().lower():
                return ""
            return nghia.strip()
    except Exception:
        return ""
    return ""

def dich_google(tu: str) -> str:
    """Dịch 1 từ sang tiếng Việt. CHỈ cache kết quả KHÔNG rỗng — nếu mạng lỗi tạm thời thì lần
    tra sau sẽ THỬ LẠI thay vì trả "" mãi mãi (khắc phục lỗi từ A1/A2 bị kẹt "Đang tải nghĩa").
    Nếu Google lỗi (429/bị chặn/treo) thì tự động chuyển sang MyMemory để nghĩa vẫn hiện ra."""
    if tu in CACHE_DICH:
        return CACHE_DICH[tu]
    nghia = ""
    try:
        r = PHIEN_DICH.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "vi", "dt": "t", "q": tu},
            timeout=5,
        )
        if r.ok and r.json():
            nghia = "".join(doan[0] for doan in r.json()[0] if doan and doan[0])
    except Exception:
        nghia = ""
    if not nghia:
        # Google lỗi (429/bị chặn/treo mạng) -> dự phòng MyMemory để nghĩa vẫn hiện ra
        nghia = dich_mymemory(tu)
    if nghia:
        CACHE_DICH[tu] = nghia
    return nghia

def dich_google_hang_loat(cac_tu) -> dict:
    """Dịch SONG SONG + GỘP NHIỀU TỪ vào 1 request Google (nhiều dòng cách nhau \n).
    ~30 từ chỉ mất 1 request (~0.7s) thay vì 30 request — nhanh gấp nhiều lần.
    Dùng cho /phan-tich-bai-doc và /tu-dien-ho-tro (vá dữ liệu bài cũ)."""
    if not cac_tu:
        return {}
    cac_tu = list(dict.fromkeys(cac_tu))  # bỏ trùng, giữ thứ tự
    ket_qua = {}
    cac_me = [cac_tu[i:i + 30] for i in range(0, len(cac_tu), 30)]  # chia mẻ 30 từ / request

    def xu_ly_me(me):
        ban_dich = {}
        try:
            r = PHIEN_DICH.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "en", "tl": "vi", "dt": "t", "q": "\n".join(me)},
                timeout=10,
            )
            if r.ok and r.json():
                for doan in r.json()[0]:
                    if doan and doan[0] and doan[1]:
                        ban_dich[doan[1].strip().lower()] = doan[0].strip()
        except Exception:
            pass
        return ban_dich

    with ThreadPoolExecutor(max_workers=min(4, len(cac_me))) as tram:
        for kq in tram.map(xu_ly_me, cac_me):
            ket_qua.update(kq)

    # Từ nào còn thiếu (Google gộp sót, hoặc Google lỗi 429/bị chặn) -> dự phòng SONG SONG.
    # dich_google đã có sẵn chế độ dự phòng MyMemory bên trong nên gọi nó là đủ — nghĩa vẫn hiện ra
    # kể cả khi Google dịch bị chặn hoàn toàn.
    con_thieu = [t for t in cac_tu if not ket_qua.get(t)]
    if con_thieu:
        def dich_1(t):
            return (t, dich_google(t))
        with ThreadPoolExecutor(max_workers=min(8, len(con_thieu))) as tram:
            for t, n in tram.map(dich_1, con_thieu):
                if n:
                    ket_qua[t] = n

    # Đổ vào cache chung — những lần tra 1 từ sau cũng siêu nhanh
    for t, n in ket_qua.items():
        if n:
            CACHE_DICH[t] = n
    return ket_qua

# 4. KHUÔN MẪU DỮ LIỆU NHẬN TỪ WEB
class ArticleRequest(BaseModel):
    text: str

# 5. TRẠM PHÂN TÍCH VÀ DỊCH THUẬT SIÊU TỐC
@app.post("/phan-tich-bai-doc")
def phan_tich(req: ArticleRequest):
    # Đưa văn bản qua bộ não spaCy để phân tách
    doc = nlp(req.text)
    
    ket_qua = []
    tu_da_loc = set()
    cac_tu_can_dich = set()  # gom các từ cần Google dịch để dịch SONG SONG 1 lượt cho nhanh

    for token in doc:
        # BỘ LỌC THÉP: Loại bỏ dấu câu, khoảng trắng, số, và TỪ CƠ BẢN (Stop words như by, in, the...)
        if token.is_punct or token.is_space or token.is_digit or token.is_stop:
            continue
        
        # Tự động cắt đuôi lấy gốc từ (vd: "originally" -> "original", "spending" -> "spend")
        tu_goc = token.lemma_.lower()
        
        # Bỏ qua những từ quá ngắn (dưới 3 chữ cái)
        if len(tu_goc) < 3:
            continue
            
        # Cấp độ chuẩn CEFR: ưu tiên bảng CSV (phủ cả A1/A2), thiếu thì dùng level trong full-word.json
        cap_do_hieu_qua = CAP_DO_CSV.get(tu_goc) or (TU_DIEN.get(tu_goc, {}).get("level") or "")

        # Chỉ giữ lại từ vựng thuộc dải B1-C2 (theo CEFR chuẩn — đồng bộ với tooltip)
        if cap_do_hieu_qua in ["B1", "B2", "C1", "C2"] and tu_goc not in tu_da_loc:
            tu_da_loc.add(tu_goc)
            
            du_lieu_tu = TU_DIEN.get(tu_goc)
            if du_lieu_tu:
                nghia_tv = du_lieu_tu["meaning"]
                
                # AUTO-TRANSLATE: Nếu từ điển không có nghĩa, đánh dấu để dịch hàng loạt bên dưới
                if not nghia_tv or nghia_tv == "Đang cập nhật":
                    cac_tu_can_dich.add(tu_goc)
                    nghia_tv = "@@CANDICH@@"

                # Đóng gói kết quả hoàn chỉnh (kèm ví dụ có sẵn từ Oxford)
                ket_qua.append({
                    "word": tu_goc,
                    "level": cap_do_hieu_qua,
                    "ipa": du_lieu_tu["ipa"],
                    "meaning": nghia_tv,
                    "example": du_lieu_tu.get("example", ""),  # Giờ có ví dụ sẵn, không phải để trống
                    "pos": pos_tieng_viet(tu_goc, du_lieu_tu.get("type", ""))  # Từ loại (danh từ/động từ...)
                })
            else:
                # Từ thuộc B1-C2 trong CSV nhưng chưa có trong full-word.json -> dịch nghĩa, ipa/ví dụ để trống
                cac_tu_can_dich.add(tu_goc)
                ket_qua.append({
                    "word": tu_goc,
                    "level": cap_do_hieu_qua,
                    "ipa": "",
                    "meaning": "@@CANDICH@@",
                    "example": "",
                    "pos": pos_tieng_viet(tu_goc)  # Từ loại suy bằng spaCy
                })
            
    # Dịch SONG SONG toàn bộ từ cần dịch (nhanh hơn hẳn dịch tuần tự)
    ban_dich = dich_google_hang_loat(cac_tu_can_dich)
    for r in ket_qua:
        if r["meaning"] == "@@CANDICH@@":
            r["meaning"] = ban_dich.get(r["word"]) or "Không thể dịch tự động."

    # Gửi trả về cho Web JavaScript
    return {"tu_vung_quan_trong": ket_qua}
# 6. TRẠM TRA CỨU NHANH (DÀNH CHO TOOLTIP VÀ CLICK CHUỘT)
@app.get("/tra-tu/{word}")
def tra_tu_nhanh(word: str):
    tu_sach = word.strip().lower()
    if not tu_sach:
        return {"word": "", "meaning": "", "ipa": "", "level": "", "example": "", "audio": ""}
    
    # BƯỚC 0: Nếu đã tra từ này rồi -> trả về ngay từ bộ nhớ đệm (0 giây, không gọi mạng)
    if tu_sach in CACHE_TRA_TU:
        return CACHE_TRA_TU[tu_sach]
    
    # 🛠️ GỌT ĐUÔI TỪ THÔNG MINH BẰNG SPACY (vd: descendants -> descendant)
    doc = nlp(tu_sach)
    tu_goc = doc[0].lemma_.lower() if len(doc) > 0 else tu_sach
    
    # Ưu tiên 1: Lấy trong RAM (từ điển B1-C2) — có IPA, ví dụ, audio sẵn.
    # ⚡ KHÔNG chặn người dùng chờ Google dịch: nghĩa (thường là "Đang cập nhật") sẽ được
    # front-end nạp RIÊNG qua /nghia/{word} — nên IPA + ví dụ hiện ra TỨC THÌ.
    du_lieu_tu = TU_DIEN.get(tu_goc) or TU_DIEN.get(tu_sach)
    if du_lieu_tu:
        nghia_goc = du_lieu_tu["meaning"]
        if not nghia_goc or nghia_goc == "Đang cập nhật":
            nghia_goc = ""
        ket_qua = {
            "word": tu_goc, 
            "meaning": nghia_goc,
            "ipa": du_lieu_tu["ipa"],
            "level": cap_do_cuoi_cung(tu_goc) or du_lieu_tu["level"],
            "example": du_lieu_tu.get("example", ""),
            "audio": du_lieu_tu.get("audio", ""),
            "pos": pos_tieng_viet(tu_goc, du_lieu_tu.get("type", ""))  # Từ loại (danh từ/động từ...)
        }
        CACHE_TRA_TU[tu_sach] = ket_qua
        return ket_qua
        
    # Ưu tiên 2: Từ ngoài từ điển (vd: A1/A2 không nằm trong full-word.json)
    # -> TRẢ NGAY cấp độ chuẩn CEFR từ CSV, KHÔNG gọi API ngoài (từng gây chậm tới 4s/lần
    #    và là nguyên nhân "rất lâu mới có nghĩa" ở các từ A1/A2). Nghĩa do /nghia nạp NỀN.
    cap_do = CAP_DO_CSV.get(tu_sach) or CAP_DO_CSV.get(tu_goc) or ""
    ket_qua = {
        "word": tu_sach,
        "meaning": "",   # nghĩa lấy RIÊNG qua /nghia/{word} — không chặn hiển thị
        "ipa": "",
        "level": cap_do,
        "example": "",
        "audio": "",
        "pos": pos_tieng_viet(tu_goc)  # Từ loại suy bằng spaCy
    }
    CACHE_TRA_TU[tu_sach] = ket_qua
    return ket_qua

# 6.2 TRẠM LẤY NGHĨA RIÊNG (KHÔNG CHẶN /tra-tu) — BẢNG CHI TIẾT NẠP NGHĨA SAU KHI CÓ IPA + VÍ DỤ
@app.get("/nghia/{word}")
def lay_nghia(word: str):
    tu = word.strip().lower()
    if not tu:
        return {"word": "", "meaning": ""}
    if tu in CACHE_NGHIA:
        return {"word": tu, "meaning": CACHE_NGHIA[tu]}
    # Gọt gốc từ (houses -> house) để dịch chuẩn và trúng cache nhiều hơn
    doc = nlp(tu)
    tu_goc = doc[0].lemma_.lower() if len(doc) > 0 else tu
    nghia = dich_google(tu_goc)
    if nghia:
        CACHE_NGHIA[tu] = nghia   # CHỈ cache khi có nghĩa — mạng lỗi thì lần sau thử lại
    return {"word": tu, "meaning": nghia}

# 6.3 TRẠM NẠP CẤP ĐỘ CEFR HÀNG LOẠT (CHO CẢ BÀI ĐỌC) — ĐỂ TÔ MÀU CHÍNH XÁC KỂ CẢ TỪ B1-C2 CHƯA CÓ TRONG DANH SÁCH CŨ
class CapDoRequest(BaseModel):
    words: list[str]

@app.post("/lay-cap-do")
def lay_cap_do(req: CapDoRequest):
    cac_tu = [w.strip().lower() for w in req.words if w.strip()]
    if not cac_tu:
        return {"levels": {}, "lemmas": {}}
    # Lemmatize theo TỪNG từ (khớp theo khoảng ký tự) — từ có nháy đơn/gạch nối vd "it's",
    # "world's", "built-in" bị spaCy tách thành nhiều token nhưng KHÔNG còn làm lệch mọi từ
    # phía sau (bug khiến temperature nhận lemma "habitation" → tô C2 sai + nghĩa sai).
    tu_goc_list, nhan_pos = lemmatize_va_pos(cac_tu)   # 1 lần spaCy cho cả bài (nhanh gấp ~100 lần)
    levels = {}
    lemmas = {}   # bản đồ dạng-trong-bài -> gốc từ chuẩn (vd "leavened" -> "leaven", "wealthier" -> "wealthy")
    # để front-end khớp BIẾN THỂ PHI HÌNH THÁI với từ trong bảng phân tích (không phụ thuộc CSV
    # có chứa đúng dạng biến thể đó hay không).
    pos = {}   # dạng-trong-bài -> từ loại tiếng Việt (để tooltip hover từ nào cũng hiện NGAY)
    for i, w in enumerate(cac_tu):
        tu_goc = tu_goc_list[i] if i < len(tu_goc_list) else w
        levels[w] = CAP_DO_CSV.get(tu_goc) or (TU_DIEN.get(tu_goc, {}).get("level") or "")
        if tu_goc and tu_goc != w:
            lemmas[w] = tu_goc
        pos[w] = pos_tieng_viet(tu_goc, TU_DIEN.get(tu_goc, {}).get("type", ""), nhan_pos.get(tu_goc, ""))
    return {"levels": levels, "lemmas": lemmas, "pos": pos}

# 6.4 TRẠM VÁ DỮ LIỆU BÀI CŨ (TRA ĐỒNG LOẠT CHO CẢ BÀI ĐỌC)
# - Từ điển tĩnh: IPA, ví dụ, audio
# - Bảng CEFR: cấp độ chuẩn
# - Google dịch GỘP MẺ (nhiều từ / 1 request): nghĩa tiếng Việt còn thiếu
# Front-end gọi khi MỞ bài (cũ lẫn mới), rồi LƯU NGƯỢC Supabase để bài cũ sửa VĨNH VIỄN.
class TuDienHoTroRequest(BaseModel):
    words: list[str]

@app.post("/tu-dien-ho-tro")
def tu_dien_ho_tro(req: TuDienHoTroRequest):
    cac_tu = []
    for w in req.words or []:
        w = (w or "").strip().lower()
        if w and w not in cac_tu:
            cac_tu.append(w)
    if not cac_tu:
        return {"results": {}}

    # Lemmatize theo TỪNG từ (khớp theo khoảng ký tự) — từ có nháy đơn/gạch nối vd "it's",
    # "world's", "built-in" bị spaCy tách thành nhiều token nhưng KHÔNG còn làm lệch mọi từ
    # phía sau (bug khiến temperature nhận nghĩa/cấp độ của habitation, difference của cosmic).
    tu_goc_list, nhan_pos = lemmatize_va_pos(cac_tu)   # 1 lần spaCy cho cả bài

    ket_qua = {}
    can_dich = set()
    for i, tu in enumerate(cac_tu):
        tu_goc = tu_goc_list[i] if i < len(tu_goc_list) else tu
        du_lieu_tu = TU_DIEN.get(tu_goc) or TU_DIEN.get(tu)
        level = cap_do_cuoi_cung(tu_goc) or cap_do_cuoi_cung(tu)
        if du_lieu_tu:
            nghia = du_lieu_tu["meaning"]
            if not nghia or nghia == "Đang cập nhật":
                nghia = ""
                can_dich.add(tu_goc)
            ket_qua[tu] = {
                "word": tu_goc,
                "meaning": nghia,
                "ipa": du_lieu_tu["ipa"],
                "level": level,
                "example": du_lieu_tu.get("example", ""),
                "audio": du_lieu_tu.get("audio", ""),
                "pos": pos_tieng_viet(tu_goc, du_lieu_tu.get("type", ""), nhan_pos.get(tu_goc, "")),
            }
        else:
            can_dich.add(tu_goc)
            ket_qua[tu] = {
                "word": tu_goc, "meaning": "", "ipa": "",
                "level": level, "example": "", "audio": "",
                "pos": pos_tieng_viet(tu_goc, nhan_spacy=nhan_pos.get(tu_goc, "")),
            }

    # Dịch GỘP MẺ toàn bộ nghĩa còn thiếu — nhanh hơn hẳn dịch từng từ
    ban_dich = dich_google_hang_loat(can_dich)
    for tu, kq in ket_qua.items():
        if not kq["meaning"]:
            kq["meaning"] = ban_dich.get(kq["word"]) or ban_dich.get(tu) or ""

    return {"results": ket_qua}

# 6.5 TRẠM AI GEMINI — API KEY ĐƯỢC GIẤU KÍN TRONG BACKEND (KHÔNG LỘ RA TRÌNH DUYỆT)
# Mẹo bảo mật: Khi public, đặt biến môi trường GEMINI_API_KEY trên server, Python sẽ ưu tiên đọc nó.
# 🔐 KHÔNG BAO GIỜ viết key cứng vào code: vừa mất an toàn, vừa bị GitHub chặn push.
# Key lấy theo thứ tự: file .env (khi chạy ở máy) → biến môi trường (khi chạy trên server).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("⚠️  Chưa có GEMINI_API_KEY — tính năng AI sẽ tạm không hoạt động.")
    print("   • Chạy ở máy : tạo file python_backend/.env với dòng GEMINI_API_KEY=...")
    print("   • Trên server: thêm biến môi trường GEMINI_API_KEY (Render → Environment).")
# Model mới nhất hợp lệ cho tài khoản này — gemini-flash-latest/gemini-2.5-flash đã bị Google
# "no longer available to new users" (404) nên không thể dùng; gemini-3.6-flash trả lời OK.
GEMINI_MODEL = "gemini-3.6-flash"


def trich_van_ban(phien_ban: dict) -> str:
    """Lấy text từ phản hồi Gemini. Model 3.x có thể chèn part 'thought' (KHÔNG có khóa
    'text') vào TRƯỚC part nội dung — nên phải tìm part ĐẦU TIÊN có text thay vì mù quáng
    lấy parts[0], nếu không json.loads() sẽ lỗi và endpoint trả rỗng."""
    try:
        for p in phien_ban["candidates"][0]["content"]["parts"]:
            if "text" in p and p["text"]:
                return p["text"]
    except Exception:
        pass
    return ""


class AiTuRequest(BaseModel):
    word: str
    mode: str = "day_du"  # "day_du" (đủ cả 3) | "nghia" (chỉ nghĩa) | "vi_du" (chỉ ví dụ)

@app.post("/ai-tra-tu")
def ai_tra_tu(req: AiTuRequest):
    tu = req.word.strip()
    if not tu:
        return {"error": "Từ rỗng."}

    # BỘ NHỚ ĐỆM: cùng từ + cùng chế độ -> không gọi Gemini lần 2 (cực nhanh)
    khoa_cache = (tu.lower(), req.mode)
    if khoa_cache in CACHE_AI:
        return CACHE_AI[khoa_cache]

    if req.mode == "nghia":
        yeu_cau = '{"ipa": "phiên âm", "meaning": "nghĩa tiếng Việt ngắn"}'
    elif req.mode == "vi_du":
        yeu_cau = '{"ipa": "phiên âm", "example": "1 câu ví dụ tiếng Anh chứa từ này"}'
    else:
        yeu_cau = '{"ipa": "phiên âm", "meaning": "nghĩa tiếng Việt ngắn", "example": "1 câu ví dụ tiếng Anh chứa từ này"}'

    prompt = f'Tra từ tiếng Anh: "{tu}". Trả về ĐÚNG 1 cục JSON duy nhất, không giải thích, không dùng markdown: {yeu_cau}'

    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=7  # Chỉ chờ tối đa 7 giây — không bao giờ treo 30 giây như trước
        )
        res.raise_for_status()
        van_ban = trich_van_ban(res.json())
        van_ban = re.sub(r"```json|```", "", van_ban).strip()
        du_lieu = json.loads(van_ban)
        ket_qua = {
            "word": tu,
            "ipa": (du_lieu.get("ipa", "") or "").strip("/"),
            "meaning": du_lieu.get("meaning", ""),
            "example": du_lieu.get("example", "")
        }
    except Exception as e:
        ket_qua = {"word": tu, "ipa": "", "meaning": "", "example": "", "error": str(e)}

    CACHE_AI[khoa_cache] = ket_qua
    return ket_qua

# 6.6 TRẠM HỌ TỪ (WORD FAMILY) — 100% OFFLINE, CHỈ TRA TỪ FILE TĨNH (KHÔNG CẦN MẠNG/GEMINI)
@app.get("/word-family/{word}")
def tra_ho_tu(word: str):
    """Trả về các biến thể cùng gốc của 1 từ (vd succeed: success/succeed/successful/successfully).
    Tra từ file tĩnh word-families.json (siêu nhanh); từ ngoài file trả [] NGAY — không bao giờ gọi Gemini."""
    tu = word.strip().lower()
    if not tu:
        return {"word": "", "family": []}
    if tu in CACHE_HO_TU:
        return CACHE_HO_TU[tu]

    # 1) Tìm trong file tĩnh — tra chính xác trước, rồi tra theo GỐC TỪ (lemma)
    gia_dinh = HO_TU.get(tu)
    tu_goc = tu
    if gia_dinh is None:
        doc = nlp(tu)
        tu_goc = doc[0].lemma_.lower() if len(doc) > 0 else tu
        gia_dinh = HO_TU.get(tu_goc)
    if gia_dinh:
        ket_qua = {"word": tu, "family": gia_dinh}
    elif tu in KHONG_CO_HO_TU or tu_goc in KHONG_CO_HO_TU:
        # 2) Đã xác nhận từ này KHÔNG có họ từ → trả [] ngay, không gọi Gemini (nhanh như file tĩnh)
        ket_qua = {"word": tu, "family": []}
    else:
        # 3) Chạy 100% OFFLINE: từ ngoài 2 file tĩnh thì trả [] NGAY — không bao giờ gọi Gemini.
        # (Trước đây từng treo 4-8 giây + phụ thuộc mạng/Google quota; giờ tra cực nhanh, ổn định.)
        ket_qua = {"word": tu, "family": []}
    CACHE_HO_TU[tu] = ket_qua
    return ket_qua


# 6.7 TRẠM NHẬN DIỆN CỤM TỪ / THÀNH NGỮ TRONG BÀI ĐỌC — 100% OFFLINE, TRA FILE TĨNH CỰC NHANH
class CumTuRequest(BaseModel):
    text: str = ""


def tim_cum_tu_loi(van_ban: str):
    """Quét văn bản, trả các cụm từ/thành ngữ/quán ngữ nằm trong cum_tu_tieng_anh.json.
    - Khớp NHIỀU TỪ liên tiếp (giữa các từ chỉ được là khoảng trắng, không vượt dấu câu).
    - Có ranh giới từ (word boundary) để không khớp nhầm vào giữa từ khác.
    - Cụm dài khớp trước; cụm ngắn rơi vào giữa cụm dài đã nhận sẽ không bị đếm trùng."""
    if not van_ban or not van_ban.strip():
        return []
    thap = van_ban.lower()
    cac_khoang_da_nhan = []  # các đoạn [đầu, cuối] đã do cụm DÀI HƠN chiếm
    ket_qua = []

    def giao_nhau(a, b):
        return not (b[0] >= a[1] or a[0] >= b[1])

    for e in CUM_TU_TIENG_ANH:
        tu = (e.get("p") or "").strip()
        if not tu:
            continue
        cac_tu = tu.split()
        mau = r"\b" + r"\s+".join(re.escape(t) for t in cac_tu) + r"\b"
        dem = 0
        for m in re.finditer(mau, thap):
            if any(giao_nhau((m.start(), m.end()), khoang) for khoang in cac_khoang_da_nhan):
                continue
            dem += 1
            cac_khoang_da_nhan.append((m.start(), m.end()))
        if dem:
            ket_qua.append({
                "cum_tu": tu,
                "loai": e.get("t", ""),
                "nghia": e.get("m", ""),
                "so_lan": dem,
            })
    return ket_qua


@app.post("/tim-cum-tu")
def tim_cum_tu(req: CumTuRequest):
    """Trả danh sách cụm từ/thành ngữ xuất hiện trong văn bản gửi lên (kèm số lần xuất hiện)."""
    return {"cum_tu": tim_cum_tu_loi((req.text or "").strip())}


# 7. TRẠM ĐỌC FILE, ẢNH OCR VÀ DỌN RÁC THÔNG MINH
@app.post("/doc-tai-lieu")
def doc_tai_lieu(file: UploadFile = File(...)):
    noi_dung_file = file.file.read()
    van_ban_tho = ""
    # file.filename có thể là None (theo kiểu FastAPI) -> phải bảo vệ trước khi gọi .lower()
    filename = (file.filename or "").lower()
    
    try:
        # 1. NẾU LÀ FILE PDF
        if filename.endswith(".pdf"):
            doc = pymupdf.open(stream=noi_dung_file, filetype="pdf")
            cac_trang = [str(page.get_text()) for page in doc]
            doc.close()

            # --- XÓA HEADER PDF LẶP Ở ĐẦU MỖI TRANG (xử lý TỪNG TRANG, an toàn tuyệt đối) ---
            # Nhiều file PDF bài IELTS lặp TÊN BÀI ở đầu mỗi trang (vd "Andrea Palladio. Italian
            # architect"). Header này thường KHÔNG có số nên regex "X 2 X" không bắt được, và sau
            # bước gộp dòng nó dính chặt vào văn bản ("...an Andrea Palladio. Italian architect
            # uncompromising exhibition..."). Cách an toàn: dòng ĐẦU TIÊN của trang nào xuất hiện
            # ở ≥ 2 trang thì đó là header trang — xóa nó khỏi đầu mọi trang (kể cả tiêu đề trùng
            # header ở trang 1). Không bao giờ đụng dòng đầu dạng nhãn đoạn "A." hoặc số trang.
            dong_dau_cac_trang = []
            for t in cac_trang:
                for d in t.split("\n"):
                    d = d.strip()
                    if not d:
                        continue
                    # Dòng đầu là nhãn đoạn ("A. ...") hoặc số trang -> trang này không có header
                    if re.match(r"^[A-J][.\s]", d) or d.isdigit():
                        break
                    dong_dau_cac_trang.append(d.lower())
                    break
            header_lap = {d for d, dem in Counter(dong_dau_cac_trang).items()
                          if dem >= 2 and len(d) <= 60}
            if header_lap:
                for i, t in enumerate(cac_trang):
                    cac_dong = t.split("\n")
                    while cac_dong and cac_dong[0].strip().lower() in header_lap:
                        cac_dong.pop(0)
                    cac_trang[i] = "\n".join(cac_dong)

            # --- NỐI CÁC TRANG THÔNG MINH ---
            # Nếu cuối trang trước kết thúc GIỮA CÂU (không có dấu câu kết thúc) thì nối liền với
            # trang sau (vd "This is an" ở cuối trang 1 + "uncompromising exhibition..." ở đầu trang
            # 2 phải thành 1 câu duy nhất sau bước gộp dòng). Nếu kết thúc bằng dấu câu (hết câu/hết
            # đoạn) thì chèn dòng trống ngăn cách đoạn — tuyệt đối không gộp 2 đoạn văn khác nhau.
            van_ban_tho = ""
            for t in cac_trang:
                t = t.strip("\n")
                if not t:
                    continue
                if van_ban_tho:
                    dong_cuoi_trang_truoc = van_ban_tho.rstrip()
                    if dong_cuoi_trang_truoc and re.search(r'[.!?"”’]\s*$', dong_cuoi_trang_truoc):
                        van_ban_tho += "\n\n"   # hết câu -> tách đoạn
                    else:
                        van_ban_tho += "\n"      # câu đứt giữa 2 trang -> nối liền (bước gộp dòng sẽ ghép)
                van_ban_tho += t
            
        # 2. NẾU LÀ FILE TEXT
        elif filename.endswith(".txt"):
            van_ban_tho = noi_dung_file.decode("utf-8")
            
        # 3. NẾU LÀ HÌNH ẢNH (KÍCH HOẠT MẮT THẦN OCR)
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            # Chuyển đổi dữ liệu ảnh thô thành mảng ma trận cho OpenCV
            nparr = np.frombuffer(noi_dung_file, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # imdecode có thể trả về None (ảnh hỏng/không hợp lệ) -> phải kiểm tra trước khi xử lý
            if img is None:
                return {"error": "Không thể đọc ảnh — file có thể bị hỏng hoặc không phải ảnh hợp lệ."}
            
            # --- Tiền xử lý ảnh (Giúp đọc ảnh chụp bị tối/mờ) ---
            # Chuyển ảnh sang dạng Trắng Đen (Grayscale)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Khử nhiễu và làm sắc nét chữ (Otsu's thresholding)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Ra lệnh cho Tesseract quét và bóc chữ từ ảnh trắng đen đó
            van_ban_tho = pytesseract.image_to_string(thresh, lang='eng')
            
        else:
            return {"error": "Hệ thống hỗ trợ file PDF, TXT và Hình ảnh (PNG/JPG)."}
            
    except Exception as e:
        return {"error": f"Lỗi đọc file/ảnh: {str(e)}"}

    # --- BỘ LỌC DỌN RÁC IELTS ĐẶC TRỊ ---
    van_ban_sach = van_ban_tho

    # Xóa câu hướng dẫn "You should spend about 20 minutes on Questions 14-26, which are based
    # on Reading Passage 1 below." ⚠️ PDF thường NGẮT DÒNG giữa câu này (vd "...Reading \nPassage 1
    # below.") nên trước đây dùng [^\n] không vượt dòng -> KHÔNG xóa được -> chữ "Question 1-13"
    # trong câu này khiến bước cắt câu hỏi ở dưới nuốt nhầm CẢ BÀI ĐỌC. Nay cho \s+ vượt dòng và
    # BUỘC kết thúc bằng "below." (câu hướng dẫn IELTS luôn kết thúc như vậy) nên an toàn tuyệt đối.
    van_ban_sach = re.sub(r'(?is)You should spend about \d+\s+minutes?\s+on\s+Questions?\s+[\d\s\-–]+.*?below\.', '', van_ban_sach)
    # Xóa tiêu đề "Reading Passage 3" / "SECTION 1" — BẮT BUỘC có số, để từ "passage" viết
    # thường trong câu (vd "this passage describes...") không bao giờ bị xóa mất.
    van_ban_sach = re.sub(r'(?i)\b(?:SECTION|READING\s+PASSAGE|PASSAGE)\s*\d+\b', '', van_ban_sach)

    # Cắt phần CÂU HỎI ở cuối bài — nhưng CHỈ khi "Questions 8-13" đứng ĐẦU DÒNG. Trước đây tìm
    # \bQuestions? bừa ở GIỮA văn bản nên khớp nhầm "Question 1-13" trong câu hướng dẫn ở ĐẦU bài
    # ("...on Question 1-13 which...") rồi CẮT SẠCH cả bài đọc. Câu hỏi IELTS luôn bắt đầu dòng
    # "Questions 8-13" nên anchor ^ ở đầu dòng là an toàn tuyệt đối.
    match = re.search(r'(?im)^\s*Questions?\s+\d+([-\sto]+\d+)?', van_ban_sach)
    if match:
        van_ban_sach = van_ban_sach[:match.start()]

    # Xóa tiêu đề PDF lặp ở ĐẦU bài — CHỈ khi 2 dòng đầu THẬT SỰ là tiêu đề (không phải đoạn văn).
    # Trước đây dùng re.sub() quét TOÀN văn bản: nếu file không có tiêu đề thì dòng đầu tiên của
    # BÀI ĐỌC (vd "A The device...") bị hiểu nhầm là tiêu đề và bị XÓA MẤT — mất nguyên đoạn A.
    def la_tieu_de_pdf(dong):
        dong = dong.strip()
        if not dong or len(dong) > 80:
            return False
        if re.match(r'^[A-J]\b', dong):   # "A The device..." là đoạn văn có nhãn, không phải tiêu đề
            return False
        if re.search(r'[.!?]["”’]?\s*$', dong):  # kết thúc bằng dấu câu -> là câu văn
            return False
        return True

    # Header PDF lặp trong CÙNG 1 dòng dạng "Tiêu đề 2 Tiêu đề" — chắc chắn là header, xóa luôn
    # (kể cả khi dòng kế tiếp là đoạn A của bài đọc). Chỉ áp dụng cho TOÀN DÒNG khớp "X N X" nên
    # tuyệt đối không ăn nhầm chữ của đoạn văn.
    van_ban_sach = re.sub(r'(?im)^\s*(.{8,}?)\s+\d+\s+\1\s*$', '', van_ban_sach)

    lines = [line.strip() for line in van_ban_sach.split('\n') if len(line.strip()) > 5]
    if len(lines) >= 2 and la_tieu_de_pdf(lines[0]) and la_tieu_de_pdf(lines[1]):
        title_1 = re.escape(lines[0])
        title_2 = re.escape(lines[1])
        # Chỉ xóa ở ĐẦU văn bản (^), không xóa tràn toàn bài — tránh ăn nhầm chữ trùng tên trong đoạn
        van_ban_sach = re.sub(fr'^\s*{title_1}(\s+\d+)?\b', '', van_ban_sach, flags=re.IGNORECASE)
        van_ban_sach = re.sub(fr'^\s*{title_2}(\s+\d+)?\b', '', van_ban_sach, flags=re.IGNORECASE)
        
    # (Đã XÓA bước "bỏ số lẫn giữa chữ" — trước đây nó nuốt mất số liệu THẬT của bài đọc:
    #  "over 70 per cent" -> "over per cent", "in 1998 the" -> "in the", "20 minutes" -> "minutes".
    #  Header PDF lặp dạng "Tiêu đề 2 Tiêu đề" đã được xóa an toàn ở bước dòng "X N X" ở trên,
    #  nên bước này hoàn toàn không cần thiết.)
    
    # Nhãn đoạn A-J đứng đầu dòng riêng: "A\nText..." -> "A. Text..." (tránh mất nhãn khi PDF để
    # nhãn riêng dòng). ⚠️ PHẢI chạy TRƯỚC bước gộp dòng — nếu chạy sau thì "A\nText" đã bị gộp
    # thành "A Text" nên nhãn bị nuốt mất (vd "on A Vicenza is..." thay vì "on\n\nA. Vicenza is...").
    van_ban_sach = re.sub(r"^([A-J])[.\s]*\n(?=[A-Z0-9'\"‘“])", r'\1. ', van_ban_sach, flags=re.M)

    van_ban_sach = re.sub(r'(?<!\n)\n(?!\n)', ' ', van_ban_sach)
    # Nhãn A-J nằm giữa câu: "...text. A Next..." -> "...text.\n\nA. Next..."
    # ⚠️ CHỈ tách khi nhãn đứng SAU DẤU CÂU kết thúc câu (., !, ?) — không bao giờ sau chữ thường/số.
    # Trước đây nhóm bắt chứa [a-z0-9] nên bất kỳ cụm "chữ thường A-J chữ hoa" (vd "in A City",
    # "to A Place", "is A Great") đều bị chèn "\n\n" — làm văn bản nát bấy. Nay chỉ tách sau
    # dấu câu và sau nhãn phải là chữ hoa nên an toàn tuyệt đối với mọi bài đọc.
    van_ban_sach = re.sub(r'([.!?]["\'”’]?)\s*([A-J])\s*\.?\s+(?=[A-Z\'"‘“])', lambda m: m.group(1) + '\n\n' + m.group(2) + '. ', van_ban_sach)
    # Nhãn đoạn bị dính sau tiêu đề/đầu câu KHÔNG có dấu câu (vd "...years on A. Vicenza is..."):
    # tách khi nhãn có dấu chấm "A." và theo sau là chữ hoa. An toàn tuyệt đối — không đụng tới
    # "in A City" (sau A không có dấu chấm), không đụng "section A.1", "Q. A famous...".
    van_ban_sach = re.sub(r'([a-z0-9])\s+([A-J])\.\s+(?=[A-Z\'"‘“])', lambda m: m.group(1) + '\n\n' + m.group(2) + '. ', van_ban_sach)
    
    van_ban_sach = re.sub(r' {2,}', ' ', van_ban_sach)
    van_ban_sach = re.sub(r'\n{3,}', '\n\n', van_ban_sach)

    # ⚠️ BÁO LỖI RÕ RÀNG nếu không đọc được chữ nào — trước đây trả text_sach rỗng làm ô
    # nội dung để trống (chỉ có tiêu đề từ tên file) và web cứ báo "vui lòng nhập nội dung".
    if not van_ban_sach.strip():
        return {"error": "Không đọc được chữ nào từ file — PDF có thể không có lớp chữ (bản scan chỉ là ảnh) hoặc ảnh quá mờ. Hãy thử file có chữ chọn được, ảnh rõ nét hơn, hoặc dán văn bản trực tiếp vào ô."}

    return {"text_sach": van_ban_sach.strip()}


# ============================================================
# 🇨🇳 TÍNH NĂNG TIẾNG TRUNG — MÔ-ĐUN RIÊNG BIỆT (KHÔNG ĐỤNG VÀO TIẾNG ANH)
# Tất cả route của bản tiếng Trung đều có tiền tố /cn và nằm trong cn_module.py
# ============================================================
from cn_module import router as cn_router

app.include_router(cn_router, prefix="/cn")


# ============================================================
# 🌐 PHỤC VỤ GIAO DIỆN WEB TRÊN CÙNG TÊN MIỀN (tùy chọn)
# Chỉ kích hoạt khi tồn tại thư mục public/ do Dockerfile tạo lúc deploy.
# Chạy local KHÔNG có public/ => KHÔNG mount => hành vi cũ giữ nguyên 100%.
# ============================================================
try:
    from fastapi.staticfiles import StaticFiles

    _thu_muc_public = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
    if os.path.isdir(_thu_muc_public):
        app.mount("/", StaticFiles(directory=_thu_muc_public, html=True), name="giao-dien")
        print(f"🌐 Đang phục vụ giao diện web tại '/' từ: {os.path.abspath(_thu_muc_public)}")
    else:
        print("ℹ️  Không thấy thư mục public/ — bỏ qua phục vụ giao diện (chạy local dùng Live Server).")
except Exception as _loi_mount:
    print(f"⚠️ Không mount được giao diện tĩnh: {_loi_mount}")