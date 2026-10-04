# -*- coding: utf-8 -*-
"""Tiền xử lý dữ liệu HSK (11.470 từ) -> hsk.json gọn:
{ từ_giản: {"lv": 1..7, "py": "pinyin", "hv": "âm Hán Việt", "trad": "phồn", "mean": "nghĩa Anh"} }
- Cấp độ ưu tiên HSK 3.0 (newest-1..7) -> new-X -> old-X. Level 7 = bậc 7-9.
- Âm Hán Việt tính sẵn từ hanviet.json (giản -> phồn -> âm đọc).
Chạy 1 lần:  python3 tao_hsk.py
"""
import json
import os

DUONG = os.path.dirname(os.path.abspath(__file__))

# 1. Nạp Âm Hán Việt
with open(os.path.join(DUONG, "hanviet.json"), encoding="utf-8") as f:
    HAN_VIET = json.load(f)

def hv_cua_chu(chu):
    """Âm Hán Việt của 1 chữ: khớp pinyin nếu có, không thì dùng âm đầu tiên."""
    bang = HAN_VIET.get(chu)
    if not bang:
        return None
    if "*" in bang:
        return bang["*"][0]
    # Ưu tiên đọc pinyin chuẩn "xue2" nếu có, không thì âm đầu tiên
    for k in sorted(bang.keys()):
        if k not in ("*",):
            vals = bang[k]
            if vals:
                return vals[0]
    return None

def han_viet_cua_tu(tu):
    am = [hv_cua_chu(c) for c in tu]
    return " ".join(a for a in am if a)

# 2. Nạp HSK thô
with open(os.path.join(DUONG, "hsk-full.json"), encoding="utf-8") as f:
    hsk_tho = json.load(f)

THU_TU_LEVEL = ["newest-1","newest-2","newest-3","newest-4","newest-5","newest-6","newest-7",
                "new-1","new-2","new-3","new-4","new-5","new-6","new-7",
                "old-1","old-2","old-3","old-4","old-5","old-6"]

ket_qua = {}
for w in hsk_tho:
    simp = w.get("simplified", "")
    if not simp:
        continue
    tap_level = set(w.get("level", []))
    lv = None
    for k in THU_TU_LEVEL:
        if k in tap_level:
            lv = int(k.rsplit("-", 1)[1])
            break
    if lv is None:
        continue
    trad = simp
    pinyin = ""
    mean_en = ""
    forms = w.get("forms", [])
    if forms:
        f0 = forms[0]
        trad = f0.get("traditional", simp)
        tr = f0.get("transcriptions", {}) or {}
        pinyin = tr.get("pinyin", "") or tr.get("numeric", "")
        mean_en = "; ".join(f0.get("meanings", [])[:3])
    ket_qua[simp] = {
        "lv": lv,
        "py": pinyin,
        "hv": han_viet_cua_tu(simp),
        "trad": trad,
        "mean": mean_en,
    }

with open(os.path.join(DUONG, "hsk.json"), "w", encoding="utf-8") as f:
    json.dump(ket_qua, f, ensure_ascii=False)

print(f"✅ Đã tạo hsk.json: {len(ket_qua)} từ HSK")

# Kiểm tra nhanh
for tu in ["学习", "你好", "中国", "朋友", "喜欢", "因为"]:
    w = ket_qua.get(tu)
    print(f"  {tu}: {w}")
