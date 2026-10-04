# -*- coding: utf-8 -*-
"""
PREFILL HỌ TỪ BẰNG GEMINI (OFFLINE, CHẠY 1 LẦN)
=================================================
- Tìm từ còn thiếu họ từ (có trong full-word.json nhưng không có trong word-families.json).
- Gọi Gemini theo MẺ 10 từ / request với generationConfig responseMimeType=json
  (nhanh hơn hẳn mặc định: ~3-4s/từ thay vì timeout 7s ở runtime).
- Họ từ hợp lệ (>= 2 từ THẬT phân biệt, mọi member nằm trong từ điển WordNet/app)
  → merge vào word-families.json.
- Từ Gemini xác nhận KHÔNG có họ → ghi vào tu-khong-co-ho-tu.json để backend trả [] NGAY,
  không bao giờ gọi Gemini ở runtime.
- Chạy song song, có retry + lưu tiến độ (prefill-progress.json) để chạy lại không mất công.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from nltk.corpus import wordnet as wn

# ---- Pace toàn cục: quota thực tế chỉ ~1 request/50s → cách nhau PACE_GIAT giây ----
KHOA_PACE = threading.Lock()
LAN_CUOI = [0.0]


def cho_phep_request():
    """Chặn để tối đa 1 request mỗi PACE_GIAT giây."""
    with KHOA_PACE:
        hieu = time.time() - LAN_CUOI[0]
        if hieu < PACE_GIAT:
            time.sleep(PACE_GIAT - hieu)
        LAN_CUOI[0] = time.time()


DUONG = os.path.dirname(os.path.abspath(__file__))

# 🌱 Nạp file .env cùng thư mục (nếu có) — khỏi phải export key thủ công mỗi lần chạy.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(DUONG, ".env"))
except Exception:
    pass

# 🔐 KHÔNG viết key cứng vào code: vừa mất an toàn, vừa bị GitHub chặn push.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise SystemExit(
        "❌ Chưa có GEMINI_API_KEY.\n"
        "   Tạo file python_backend/.env với 1 dòng:\n"
        "       GEMINI_API_KEY=key_cua_ban"
    )
GEMINI_MODEL = "gemini-3.6-flash"
ME = 10          # số từ mỗi request Gemini
SO_LUONG = 1     # SERIAL — quota free tier thực tế chỉ ~1 request/50s (bucket cạn sau lần bắn 8 luồng)
TIMEOUT = 45     # chờ tối đa mỗi request (Gemini đôi khi chậm 10-40s)
RETRY = 2        # số lần gọi lại khi lỗi
PACE_GIAT = 50   # cách nhau tối thiểu giữa 2 request (giây)

# Từ chức năng không bao giờ có họ từ trong định dạng app (chỉ nhận từ ĐƠN) → đánh dấu offline
POS_KHONG_CO_HO = {
    "pronoun", "preposition", "conjunction", "modal verb", "determiner",
    "exclamation", "number", "ordinal number", "auxiliary verb",
    "infinitive marker", "definite article", "indefinite article", "linking verb",
}

# ---------- TỪ ĐIỂN HỢP LỆ (giống bo_sung_word_families_rules.py) ----------
TU_VUNG = set()
LOAI_TU = {}
with open(os.path.join(DUONG, "full-word.json"), encoding="utf-8") as f:
    for item in json.load(f):
        val = item.get("value", {})
        w = (val.get("word") or "").strip().lower()
        if w:
            TU_VUNG.add(w)
            t = (val.get("type") or "").strip()
            if t:
                LOAI_TU[w] = t

duong_csv = os.path.join(DUONG, "..", "..", "ENGLISH_CERF_WORDS.csv")
if os.path.exists(duong_csv):
    with open(duong_csv, encoding="utf-8") as f:
        next(f, None)
        for dong in f:
            dong = dong.strip()
            if not dong:
                continue
            phan = dong.rsplit(",", 1)
            if len(phan) == 2:
                for b in phan[0].strip().lower().split("/"):
                    if b:
                        TU_VUNG.add(b)

print("⏳ Đang xây từ điển WordNet (155k từ)...")
VN_WORDS = set(TU_VUNG)
for s in wn.all_synsets():
    for l in s.lemmas():
        w = l.name().replace("_", " ").lower()
        if w and w.replace("-", "").isalpha() and " " not in w:
            VN_WORDS.add(w)
print(f"✅ Từ điển hợp lệ: {len(VN_WORDS)} từ")


def la_tu_don(tu):
    return bool(tu) and tu.replace("-", "").isalpha() and " " not in tu


# ---------- GỌI GEMINI (1 mẹ từ) ----------
def goi_gemini(cac_tu):
    """Trả về dict {từ: [ [word, pos], ... ]} — lỗi thì ném Exception để retry."""
    prompt = (
        f"Với TỪNG từ trong danh sách dưới đây, cho họ từ (word family) gồm các biến thể CÙNG GỐC "
        f"(danh từ, động từ, tính từ, trạng từ). Không có biến thể nào thì chỉ liệt kê chính từ đó. "
        f"Trả về ĐÚNG 1 cục JSON duy nhất, không markdown, không giải thích, khóa là từng từ: "
        f'{{"afternoon": [{{"word": "afternoon", "pos": "danh từ"}}], "apple": [...]}}\n\n{cac_tu}'
    )
    cho_phep_request()
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 3000},
        },
        timeout=TIMEOUT,
    )
    if r.status_code == 429:
        # Free tier chỉ 20 request/phút — phải chờ quota hồi phục rồi thử lại
        nghi = 60
        import re as _re
        m = _re.search(r"retry in ([\d.]+)s", r.text)
        if m:
            nghi = min(float(m.group(1)) + 3, 120)
        raise RateLimited(nghi)
    r.raise_for_status()
    van_ban = ""
    for p in r.json().get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "text" in p and p["text"]:
            van_ban = p["text"]
            break
    van_ban = re.sub(r"```json|```", "", van_ban).strip()
    du_lieu = json.loads(van_ban)
    if not isinstance(du_lieu, dict):
        raise ValueError("Gemini trả về không phải object JSON")
    return du_lieu


def chuan_hoa(word, raw):
    """Chuẩn hóa 1 mục gia_đình do Gemini trả → [(word, pos), ...] (chỉ từ THẬT)."""
    if isinstance(raw, str):          # Gemini trả chuỗi "word" thay vì object
        return [(raw.strip().lower(), "")]
    ket = []
    if isinstance(raw, list):
        for e in raw:
            if isinstance(e, str):
                w = e.strip().lower()
                ket.append((w, ""))
            elif isinstance(e, dict):
                w = (e.get("word") or "").strip().lower()
                p = (e.get("pos") or "").strip()
                if w:
                    ket.append((w, p))
    # lọc: chỉ giữ từ THẬT + bỏ trùng word trùng pos
    da_thay = set()
    sach = []
    for w, p in ket:
        if not la_tu_don(w) or w not in VN_WORDS:
            continue
        khoa = (w, p)
        if khoa in da_thay:
            continue
        da_thay.add(khoa)
        sach.append([w, p])
    return sach


# ---------- NẠP TRẠNG THÁI HIỆN TẠI ----------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
duong_khong = os.path.join(DUONG, "tu-khong-co-ho-tu.json")
duong_tien_do = os.path.join(DUONG, "prefill-progress.json")

with open(duong_ho_tu, encoding="utf-8") as f:
    HO_TU = json.load(f)

KHONG_CO = set()
if os.path.exists(duong_khong):
    with open(duong_khong, encoding="utf-8") as f:
        KHONG_CO = set(json.load(f))

TIEN_DO = {"da_co": {}, "khong_co": []}
if os.path.exists(duong_tien_do):
    with open(duong_tien_do, encoding="utf-8") as f:
        TIEN_DO = json.load(f)


# ---------- ĐÁNH DẤU OFFLINE CÁC TỪ CHẮC CHẮN KHÔNG CÓ HỌ ----------
# Cụm từ (có khoảng trắng) hoặc từ chức năng → không thể có họ từ dạng từ ĐƠN → khỏi gọi Gemini
for w in list(LOAI_TU):
    loai_tu = (LOAI_TU.get(w) or "").lower()
    if " " in w or loai_tu in POS_KHONG_CO_HO:
        if w not in HO_TU and w not in KHONG_CO:
            KHONG_CO.add(w)
            print(f"  ➖ {w} → không có họ (offline, không tốn Gemini)")

cac_tu_con = [w for w in LOAI_TU
              if w not in HO_TU and w not in KHONG_CO and w not in TIEN_DO["da_co"]]
print(f"Còn thiếu họ từ: {len(cac_tu_con)} (sẽ gọi Gemini ~{len(cac_tu_con)//ME+1} request)")


class RateLimited(Exception):
    def __init__(self, nghi):
        super().__init__(f"rate limited, đợi {nghi:.0f}s")
        self.nghi = nghi


def xu_ly_me(me, toi_da_cho=1200):
    """Gọi Gemini 1 mẹ từ, trả {từ: family} hoặc {từ: None} (không có họ).
    KIÊN NHẪN: bị 429 thì chờ quota hồi phục rồi thử lại — không bỏ cuộc sớm."""
    bat_dau_cho = time.time()
    lan_loi_khac = 0
    while time.time() - bat_dau_cho < toi_da_cho:
        try:
            raw = goi_gemini(me)
            ket = {}
            for w in me:
                if w not in raw:
                    continue
                gia = chuan_hoa(w, raw[w])
                cac_word = [g[0] for g in gia]
                if len(set(cac_word)) >= 2:
                    ket[w] = gia
                else:
                    ket[w] = None
            return ket
        except RateLimited as e:
            print(f"    Quota can - doi {e.nghi:.0f}s cho hoi phuc...", flush=True)
            time.sleep(e.nghi)
        except Exception as e:
            lan_loi_khac += 1
            if lan_loi_khac >= 3:
                return {}
            print(f"    LOI {type(e).__name__} - thu lai sau 3s...", flush=True)
            time.sleep(3)
    return {}


# ---------- CHẠY SERIAL + LƯU TIẾN ĐỘ SAU MỖI MẺ ----------
# Chờ 60s đầu cho bucket quota hồi phục (tránh đốt lượt retry ngay lúc khởi động)
print("Dang doi 60s cho quota hoi phuc roi moi bat dau goi Gemini...", flush=True)
time.sleep(60)

cac_me = [cac_tu_con[i:i + ME] for i in range(0, len(cac_tu_con), ME)]
bat_dau = time.time()


def luu_tien_do():
    with open(duong_tien_do, "w", encoding="utf-8") as f:
        json.dump(TIEN_DO, f, ensure_ascii=False)


for chi_so, me in enumerate(cac_me, 1):
    ket = xu_ly_me(me)
    for w in me:
        if w in ket:
            if ket[w]:
                TIEN_DO["da_co"][w] = ket[w]
            else:
                TIEN_DO["khong_co"].append(w)
    luu_tien_do()   # lưu sau MỖI mẻ — chạy lại không mất công
    so_giay = int(time.time() - bat_dau)
    print(f"  ... {chi_so}/{len(cac_me)} me | {len(TIEN_DO['da_co'])} ho moi | {len(TIEN_DO['khong_co'])} khong co ho | {so_giay}s", flush=True)

# ---------- GỘP VÀO FILE ----------
if TIEN_DO["da_co"]:
    HO_TU.update(TIEN_DO["da_co"])
with open(duong_ho_tu + ".bak2", "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

if TIEN_DO["khong_co"]:
    KHONG_CO.update(TIEN_DO["khong_co"])
with open(duong_khong, "w", encoding="utf-8") as f:
    json.dump(sorted(KHONG_CO), f, ensure_ascii=False, indent=2)

# dọn file tiến độ sau khi hoàn tất (chỉ khi chạy xong)
if os.path.exists(duong_tien_do):
    os.remove(duong_tien_do)

print("\n===== KẾT QUẢ PREFILL GEMINI =====")
print(f"Họ từ mới thêm vào word-families.json: {len(TIEN_DO['da_co'])}")
print(f"Từ xác nhận KHÔNG có họ (ghi tu-khong-co-ho-tu.json): {len(TIEN_DO['khong_co'])}")
print(f"Tổng họ từ: {len(HO_TU)} | Tổng từ không có họ: {len(KHONG_CO)}")
print(f"Tổng thời gian: {int(time.time()-bat_dau)}s")
# Kiểm tra còn thiếu sót không
con_thieu = [w for w in LOAI_TU if w not in HO_TU and w not in KHONG_CO]
print(f"Còn sót chưa xử lý: {len(con_thieu)} — {con_thieu[:20]}")
