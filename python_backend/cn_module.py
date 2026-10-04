# -*- coding: utf-8 -*-
"""
TÍNH NĂNG TIẾNG TRUNG 🇨🇳 — MÔ-ĐUN RIÊNG BIỆT
=============================================
- Không đụng vào bất kỳ code tiếng Anh nào (chỉ đăng ký 1 router /cn trong main.py)
- Dữ liệu nạp sẵn:
    hsk.json      (11.470 từ HSK: cấp độ 1-9, pinyin, âm Hán Việt, chữ phồn, nghĩa Anh)
    hanviet.json  (13.224 ký tự Giản + Phồn -> Âm Hán Việt)
- Pinyin tự sinh bằng pypinyin; nghĩa tiếng Việt dịch Google (zh -> vi) GỘP MẺ.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import cv2
import jieba
import numpy as np
import pymupdf
import pytesseract
import requests
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from pypinyin import Style, lazy_pinyin

router = APIRouter()

DUONG = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 1. NẠP DỮ LIỆU VÀO RAM
# ============================================================
HSK = {}
with open(os.path.join(DUONG, "hsk.json"), encoding="utf-8") as f:
    HSK = json.load(f)
# Bảng cấp độ từng CHỮ (dự phòng cho từ ghép không nằm trong danh sách HSK)
HSK_CHAR = {k: v["lv"] for k, v in HSK.items() if len(k) == 1}
print(f"✅ [Tiếng Trung] Đã nạp {len(HSK)} từ HSK + {len(HSK_CHAR)} chữ đơn.")

# Nạp toàn bộ từ HSK vào bộ cắt từ jieba để chia từ đúng chuẩn từ điển
for _tu in HSK:
    jieba.add_word(_tu)

HAN_VIET = {}
with open(os.path.join(DUONG, "hanviet.json"), encoding="utf-8") as f:
    HAN_VIET = json.load(f)
print(f"✅ [Tiếng Trung] Đã nạp {len(HAN_VIET)} ký tự Âm Hán Việt.")

# Phiên dịch Google dùng riêng cho tiếng Trung (zh -> vi)
PHIEN_DICH_CN = requests.Session()
CACHE_DICH_CN = {}
CACHE_TRA_TU_CN = {}
CACHE_HSK = {}

# 1.5 CỤM TỪ / THÀNH NGỮ / KHẨU NGỮ TIẾNG TRUNG — FILE TĨNH BIÊN SOẠN SẴN
# Mỗi mục: {p: cụm từ (thành ngữ 4 chữ / khẩu ngữ), t: loại, m: nghĩa tiếng Việt}
CUM_TU_TIENG_TRUNG = []
duong_cum_tu_cn = os.path.join(DUONG, "cum_tu_tieng_trung.json")
if os.path.exists(duong_cum_tu_cn):
    with open(duong_cum_tu_cn, encoding="utf-8") as f:
        CUM_TU_TIENG_TRUNG = json.load(f)
    # Sắp theo số KÝ TỰ GIẢM DẦN: cụm dài khớp trước để cụm ngắn nằm bên trong không bị đếm trùng
    CUM_TU_TIENG_TRUNG.sort(key=lambda e: len(e.get("p", "")), reverse=True)
    print(f"✅ [Tiếng Trung] Đã nạp {len(CUM_TU_TIENG_TRUNG)} cụm từ/thành ngữ vào RAM!")
else:
    print("⚠️ [Tiếng Trung] Không tìm thấy cum_tu_tieng_trung.json — tính năng Cụm từ tạm tắt.")


# ============================================================
# 2. CÔNG CỤ XỬ LÝ TIẾNG TRUNG
# ============================================================
def pinyin_cua(tu: str) -> str:
    """Pinyin có dấu thanh: 学习 -> xué xí"""
    return " ".join(lazy_pinyin(tu, style=Style.TONE))


def am_han_viet_cua_chu(chu: str, pinyin_tone3: str = "") -> str:
    """Âm Hán Việt của 1 CHỮ — khớp theo pinyin trong ngữ cảnh từ (chính xác hơn)."""
    bang = HAN_VIET.get(chu)
    if not bang:
        return ""
    if pinyin_tone3 and pinyin_tone3 in bang and bang[pinyin_tone3]:
        return bang[pinyin_tone3][0]
    if "*" in bang and bang["*"]:
        return bang["*"][0]
    for vals in bang.values():
        if vals:
            return vals[0]
    return ""


def am_han_viet_cua_tu(tu: str) -> str:
    """Âm Hán Việt của TỪ: 学习 -> 'học tập'. Pinyin lấy theo ngữ cảnh cả từ."""
    if not tu:
        return ""
    cac_py = lazy_pinyin(tu, style=Style.TONE3)
    am = [am_han_viet_cua_chu(c, py) for c, py in zip(tu, cac_py)]
    return " ".join(a for a in am if a)


def cap_do_cua_tu(tu: str):
    """Cấp độ HSK (1-7). Từ ghép ngoài danh sách -> lấy cấp độ CAO nhất của các chữ thành phần."""
    w = HSK.get(tu)
    if w:
        return w["lv"]
    lvs = [HSK_CHAR[c] for c in tu if c in HSK_CHAR]
    return max(lvs) if lvs else None


def tach_tu_chua_ro(tu: str):
    """Từ jieba cắt ra KHÔNG có trong HSK (vd: '今天天气') -> thử tách thành các từ HSK
    (今天 + 天气). Chỉ chấp nhận tách khi TẤT CẢ phần con đều là từ HSK — nếu không thì
    giữ nguyên (an toàn cho tên riêng, từ ghép hiếm)."""
    if len(tu) < 2 or tu in HSK or la_dau_cau(tu):
        return [tu]
    cac_phan = []
    i = 0
    while i < len(tu):
        tim = None
        for j in range(min(len(tu), i + 6), i, -1):  # quét từ dài nhất (tối đa 6 chữ)
            if tu[i:j] in HSK:
                tim = tu[i:j]
                break
        if tim:
            cac_phan.append(tim)
            i += len(tim)
        else:
            cac_phan.append(tu[i])
            i += 1
    if all(p in HSK for p in cac_phan):
        return cac_phan
    return [tu]


def la_chu_han(chu: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", chu))


def la_dau_cau(doan: str) -> bool:
    """Dấu câu / số / ký tự đặc biệt (không chứa chữ Hán)."""
    return not la_chu_han(doan)


def dich_google_cn(tu: str) -> str:
    """Dịch 1 từ Trung -> Việt. Chỉ cache kết quả KHÔNG rỗng."""
    if tu in CACHE_DICH_CN:
        return CACHE_DICH_CN[tu]
    nghia = ""
    try:
        r = PHIEN_DICH_CN.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "zh-CN", "tl": "vi", "dt": "t", "q": tu},
            timeout=5,
        )
        if r.ok and r.json():
            nghia = "".join(doan[0] for doan in r.json()[0] if doan and doan[0])
    except Exception:
        nghia = ""
    if nghia:
        CACHE_DICH_CN[tu] = nghia
    return nghia


def dich_google_cn_hang_loat(cac_tu) -> dict:
    """Dịch SONG SONG + GỘP MẺ (30 từ / request) — nhanh gấp nhiều lần."""
    if not cac_tu:
        return {}
    cac_tu = list(dict.fromkeys(cac_tu))
    ket_qua = {}
    cac_me = [cac_tu[i:i + 30] for i in range(0, len(cac_tu), 30)]

    def xu_ly_me(me):
        ban_dich = {}
        try:
            r = PHIEN_DICH_CN.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "zh-CN", "tl": "vi", "dt": "t", "q": "\n".join(me)},
                timeout=10,
            )
            if r.ok and r.json():
                for doan in r.json()[0]:
                    if doan and doan[0] and doan[1]:
                        ban_dich[doan[1].strip()] = doan[0].strip()
        except Exception:
            pass
        for t in me:
            if t not in ban_dich:
                n = dich_google_cn(t)
                if n:
                    ban_dich[t] = n
        return ban_dich

    with ThreadPoolExecutor(max_workers=min(4, len(cac_me))) as tram:
        for kq in tram.map(xu_ly_me, cac_me):
            ket_qua.update(kq)
    for t, n in ket_qua.items():
        if n:
            CACHE_DICH_CN[t] = n
    return ket_qua


# ============================================================
# 3. TRẠM PHÂN TÍCH BÀI ĐỌC TIẾNG TRUNG
# ============================================================
class CnArticleRequest(BaseModel):
    text: str


@router.post("/phan-tich-bai-doc")
def phan_tich_cn(req: CnArticleRequest):
    van_ban = (req.text or "").strip()
    if not van_ban:
        return {"tokens": [], "vocab": []}

    # 1) CẮT TỪ bằng jieba — trả về MẢNG TOKEN, JS chỉ việc in ra
    tokens = []
    for doan in jieba.cut(van_ban):
        if not doan.strip():
            # Giữ xuống dòng để trình duyệt còn phân đoạn văn bản
            if "\n" in doan:
                tokens.append({"t": "\n", "type": "br"})
            continue
        if la_dau_cau(doan):
            tokens.append({"t": doan, "type": "punct"})
        else:
            # Tách thêm từ ghép lạ không nằm trong HSK (今天天气 -> 今天 + 天气)
            for phan in tach_tu_chua_ro(doan):
                tokens.append({
                    "t": phan,
                    "p": pinyin_cua(phan),
                    "hv": am_han_viet_cua_tu(phan),
                    "lv": cap_do_cua_tu(phan),
                    "type": "word",
                })

    # 2) BẢNG TỪ VỰNG QUAN TRỌNG: từ HSK + từ ghép 2+ chữ (bỏ hạt ngữ pháp đơn lẻ)
    vocab = []
    da_thay = {}
    for tok in tokens:
        if tok["type"] != "word":
            continue
        w = tok["t"]
        if w in da_thay:
            continue
        hs = HSK.get(w)
        if not hs and len(w) == 1:
            continue  # chữ đơn không thuộc HSK = hạt ngữ pháp (的, 了, 吗...)
        da_thay[w] = True
        vocab.append({
            "word": w,
            "pinyin": tok["p"],
            "hanviet": tok["hv"],
            "level": str(tok["lv"]) if tok["lv"] else "",
            "trad": hs["trad"] if hs else "",
            "mean_en": hs["mean"] if hs else "",
            "meaning": "",
        })

    # 3) DỊCH NGHĨA TIẾNG VIỆT GỘP MẺ
    ban_dich = dich_google_cn_hang_loat([v["word"] for v in vocab])
    for v in vocab:
        v["meaning"] = ban_dich.get(v["word"]) or ""

    return {"tokens": tokens, "vocab": vocab}


# ============================================================
# 4. TRA TỪ NHANH (TOOLTIP / CLICK)
# ============================================================
@router.get("/tra-tu/{word}")
def tra_tu_cn(word: str):
    tu = word.strip()
    if not tu:
        return {"word": "", "pinyin": "", "hanviet": "", "level": "", "trad": "", "meaning": ""}
    if tu in CACHE_TRA_TU_CN:
        return CACHE_TRA_TU_CN[tu]

    w = HSK.get(tu)
    ket_qua = {
        "word": tu,
        "pinyin": pinyin_cua(tu),
        "hanviet": am_han_viet_cua_tu(tu),
        "level": str(cap_do_cua_tu(tu)) if cap_do_cua_tu(tu) else "",
        "trad": w["trad"] if w else "",
        "meaning": "",
    }
    CACHE_TRA_TU_CN[tu] = ket_qua
    return ket_qua


# ============================================================
# 5. NGHĨA TIẾNG VIỆT RIÊNG (KHÔNG CHẶN /tra-tu)
# ============================================================
@router.get("/nghia/{word}")
def lay_nghia_cn(word: str):
    tu = word.strip()
    if not tu:
        return {"word": "", "meaning": ""}
    if tu in CACHE_DICH_CN:
        return {"word": tu, "meaning": CACHE_DICH_CN[tu]}
    nghia = dich_google_cn(tu)
    return {"word": tu, "meaning": nghia}


# ============================================================
# 6. NẠP CẤP ĐỘ HSK HÀNG LOẠT (TÔ MÀU CHÍNH XÁC)
# ============================================================
class CnLevelRequest(BaseModel):
    words: list[str]


@router.post("/lay-hsk")
def lay_cap_do_cn(req: CnLevelRequest):
    cac_tu = [w.strip() for w in req.words if w.strip()]
    levels = {}
    for w in cac_tu:
        lv = cap_do_cua_tu(w)
        levels[w] = str(lv) if lv else ""
    return {"levels": levels}


# ============================================================
# 6.5 🧩 TỪ GHÉP CỦA MỘT CHỮ HÁN (BẤM CHỮ → XEM CÁC TỪ GHÉP CHỨA CHỮ ĐÓ)
# Dữ liệu lấy 100% từ hsk.json (11.470 từ) — offline, không cần dịch Google.
# ============================================================
@router.get("/tu-ghep/{chu}")
def tu_ghep_cn(chu: str):
    """Trả các từ HSK 2–4 chữ có chứa `chu`, sắp cấp độ DỄ → KHÓ (HSK1 trước HSK9)."""
    chu = chu.strip()
    if not chu or not la_chu_han(chu) or len(chu) != 1:
        return {"chu": chu, "tong": 0, "results": []}

    ket_qua = []
    for tu, w in HSK.items():
        if 2 <= len(tu) <= 4 and chu in tu:
            ket_qua.append({
                "word": tu,
                "pinyin": (w.get("py") or "").strip() or pinyin_cua(tu),
                "hanviet": (w.get("hv") or "").strip() or am_han_viet_cua_tu(tu),
                "level": str(w.get("lv")) if w.get("lv") else "",
                "trad": w.get("trad", "") or "",
                "mean_en": w.get("mean", "") or "",
            })

    ket_qua.sort(
        key=lambda k: (
            int(k["level"]) if k["level"].isdigit() else 99,
            0 if k["word"].startswith(chu) else 1,   # từ mở đầu bằng chữ này xếp trước cùng cấp
            len(k["word"]),
        )
    )
    return {"chu": chu, "tong": len(ket_qua), "results": ket_qua[:12]}


# ============================================================
# 7. VÁ DỮ LIỆU BÀI CŨ (TRA ĐỒNG LOẠT)
# ============================================================
class CnTuDienHoTroRequest(BaseModel):
    words: list[str]


@router.post("/tu-dien-ho-tro")
def tu_dien_ho_tro_cn(req: CnTuDienHoTroRequest):
    cac_tu = []
    for w in req.words or []:
        w = (w or "").strip()
        if w and w not in cac_tu:
            cac_tu.append(w)
    if not cac_tu:
        return {"results": {}}

    ket_qua = {}
    for tu in cac_tu:
        w = HSK.get(tu)
        ket_qua[tu] = {
            "word": tu,
            "pinyin": pinyin_cua(tu),
            "hanviet": am_han_viet_cua_tu(tu),
            "level": str(cap_do_cua_tu(tu)) if cap_do_cua_tu(tu) else "",
            "trad": w["trad"] if w else "",
            "mean_en": w["mean"] if w else "",
            "meaning": "",
        }

    ban_dich = dich_google_cn_hang_loat(cac_tu)
    for tu, kq in ket_qua.items():
        kq["meaning"] = ban_dich.get(tu) or ""
    return {"results": ket_qua}


# ============================================================
# 7.6 NHẬN DIỆN CỤM TỪ / THÀNH NGỮ TRONG BÀI ĐỌC (100% OFFLINE — TRA FILE TĨNH)
# ============================================================
class CumTuRequestCn(BaseModel):
    text: str = ""


def tim_cum_tu_cn(van_ban: str):
    """Quét văn bản, trả các cụm từ/thành ngữ/khẩu ngữ trong cum_tu_tieng_trung.json.
    Cụm dài khớp trước; cụm ngắn nằm gọn trong cụm dài đã nhận sẽ không bị đếm trùng."""
    if not van_ban or not van_ban.strip():
        return []
    cac_khoang = []  # các đoạn [đầu, cuối] đã do cụm DÀI HƠN chiếm
    ket_qua = []

    def giao_nhau(a, b):
        return not (b[0] >= a[1] or a[0] >= b[1])

    for e in CUM_TU_TIENG_TRUNG:
        tu = (e.get("p") or "").strip()
        if not tu:
            continue
        dem = 0
        i = 0
        while True:
            j = van_ban.find(tu, i)
            if j < 0:
                break
            kt = j + len(tu)
            if any(giao_nhau((j, kt), khoang) for khoang in cac_khoang):
                i = j + 1
                continue
            dem += 1
            cac_khoang.append((j, kt))
            i = kt
        if dem:
            ket_qua.append({
                "cum_tu": tu,
                "loai": e.get("t", ""),
                "nghia": e.get("m", ""),
                "pinyin": pinyin_cua(tu),
                "hanviet": am_han_viet_cua_tu(tu),
                "so_lan": dem,
            })
    return ket_qua


@router.post("/tim-cum-tu")
def tim_cum_tu_cn_api(req: CumTuRequestCn):
    """Trả danh sách cụm từ/thành ngữ xuất hiện trong văn bản tiếng Trung gửi lên."""
    return {"cum_tu": tim_cum_tu_cn((req.text or "").strip())}


# ============================================================
# 8. ĐỌC FILE / OCR TIẾNG TRUNG (chi_sim / chi_tra)
# ============================================================
@router.post("/doc-tai-lieu")
def doc_tai_lieu_cn(file: UploadFile = File(...), lang: str = "chi_sim"):
    noi_dung_file = file.file.read()
    van_ban_tho = ""
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".pdf"):
            doc = pymupdf.open(stream=noi_dung_file, filetype="pdf")
            for page in doc:
                van_ban_tho += str(page.get_text()) + "\n"
            doc.close()
        elif filename.endswith(".txt"):
            van_ban_tho = noi_dung_file.decode("utf-8")
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            nparr = np.frombuffer(noi_dung_file, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {"error": "Không thể đọc ảnh — file có thể bị hỏng hoặc không phải ảnh hợp lệ."}
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            ngo_ngu = lang if lang in ("chi_sim", "chi_tra") else "chi_sim"
            van_ban_tho = pytesseract.image_to_string(thresh, lang=ngo_ngu)
        else:
            return {"error": "Hệ thống hỗ trợ file PDF, TXT và Hình ảnh (PNG/JPG)."}
    except Exception as e:
        return {"error": f"Lỗi đọc file/ảnh: {str(e)}"}

    # Dọn dẹp văn bản tiếng Trung: bỏ khoảng trắng giữa các chữ Hán, gộp dòng trống
    van_ban_sach = van_ban_tho
    van_ban_sach = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", van_ban_sach)
    van_ban_sach = re.sub(r"(?<!\n)\n(?!\n)", " ", van_ban_sach)
    van_ban_sach = re.sub(r"\n{3,}", "\n\n", van_ban_sach)
    van_ban_sach = re.sub(r" {2,}", " ", van_ban_sach)

    return {"text_sach": van_ban_sach.strip()}
