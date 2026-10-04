# -*- coding: utf-8 -*-
"""Tiền xử lý dữ liệu Âm Hán Việt:
- hanviet-data.js  -> dict {chữ_phồn: {pinyin: [âm Hán Việt]}}
- STCharacters.txt -> ánh xạ Giản -> Phồn

Kết quả: hanviet.json gồm CẢ giản thể lẫn phồn thể, pinyin chuẩn hoá sang
kiểu pypinyin TONE3 (ü -> v, u: -> v), giữ wildcard "*".
Chạy 1 lần duy nhất:  python3 tao_hanviet.py
"""
import json
import os

DUONG = os.path.dirname(os.path.abspath(__file__))

# 1. Đọc hanvietData.js (JSON nằm sau dòng export)
with open(os.path.join(DUONG, "hanviet-data.js"), encoding="utf-8") as f:
    content = f.read()
data = json.loads(content[content.index("{"):])  # {trad: {pinyin: [âm]}}

# 2. Đọc ánh xạ Giản -> Phồn
sang_phon = {}
with open(os.path.join(DUONG, "STCharacters.txt"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            sang_phon[parts[0]] = parts[1]

# 3. Chuẩn hoá pinyin: ü/u: -> v (khớp pypinyin Style.TONE3)
def chuan_pinyin(pi):
    return pi.replace("ü", "v").replace("u:", "v")

# 4. Dựng từ điển cuối cùng
ket_qua = {}
for chu, bang_pinyin in data.items():
    bang_moi = {chuan_pinyin(k) if k != "*" else "*": v for k, v in bang_pinyin.items()}
    ket_qua[chu] = bang_moi
    # Thêm biến thể Giản thể trỏ về cùng dữ liệu
    for gian, phon in sang_phon.items():
        if phon == chu:
            ket_qua.setdefault(gian, bang_moi)

# 5. Lưu
with open(os.path.join(DUONG, "hanviet.json"), "w", encoding="utf-8") as f:
    json.dump(ket_qua, f, ensure_ascii=False)

print(f"✅ Đã tạo hanviet.json: {len(ket_qua)} ký tự (giản + phồn)")

# 6. Kiểm tra nhanh
def hv(chu):
    bang = ket_qua.get(chu, {})
    return bang.get("lv4") or bang.get("*") or list(bang.values())[0] if bang else None

for c in ["学", "习", "国", "绿", "语", "爱", "时"]:
    print(f"  {c} → {hv(c)}")
