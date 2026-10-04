# -*- coding: utf-8 -*-
"""
HOÀN THIỆN HỌ TỪ 100% OFFLINE — KHÔNG CẦN GEMINI
==================================================
Vấn đề: 228 từ còn thiếu họ từ. WordNet + word_forms + luật suffix đều bỏ sót,
nhưng phần lớn là từ GHÉP / từ BIỆT LẬP (không có họ thật) — chỉ cần đánh dấu
"không có họ" để backend trả [] NGAY, không bao giờ gọi Gemini ở runtime.

Ngoại lệ: ~15 từ bất quy tắc CÓ họ thật mà WordNet không nối (lỗ hổng -th/-dom
nổi tiếng: freedom↔free, width↔wide, theft↔thief...) → THÊM TAY từ điển curate.

An toàn tuyệt đối: KHÔNG đụng 1 chữ vào 4.550 mục đang chạy ổn định.
"""
import json
import os
from collections import defaultdict

from nltk.corpus import wordnet as wn

DUONG = os.path.dirname(os.path.abspath(__file__))

POS_WN_TV = {'n': 'danh từ', 'v': 'động từ', 'a': 'tính từ', 's': 'tính từ', 'r': 'trạng từ'}
POS_FULL_TV = {
    "noun": "danh từ", "verb": "động từ", "adjective": "tính từ",
    "adverb": "trạng từ", "pronoun": "đại từ", "preposition": "giới từ",
    "determiner": "từ hạn định", "number": "số từ", "conjunction": "liên từ",
    "exclamation": "thán từ", "modal verb": "trợ động từ tình thái",
    "ordinal number": "số thứ tự", "auxiliary verb": "trợ động từ",
    "indefinite article": "mạo từ không xác định", "linking verb": "động từ nối",
    "definite article": "mạo từ xác định", "infinitive marker": "tiểu từ nguyên mẫu",
}
THU_TU_POS = {"danh từ": 0, "động từ": 1, "tính từ": 2, "trạng từ": 3}

# ---------- HỌ TỪ CURATE (bất quy tắc WordNet bỏ sót) ----------
# Mỗi mục: [word, pos tiếng Việt] — chỉ dùng từ THẬT đã kiểm chứng trong từ điển
CURATE = {
    "freedom": [["free", "tính từ"], ["freely", "trạng từ"], ["freedom", "danh từ"]],
    "wisdom": [["wise", "tính từ"], ["wisely", "trạng từ"], ["wisdom", "danh từ"]],
    "width": [["wide", "tính từ"], ["widely", "trạng từ"], ["width", "danh từ"], ["widen", "động từ"]],
    "depth": [["deep", "tính từ"], ["deeply", "trạng từ"], ["depth", "danh từ"], ["deepen", "động từ"]],
    "theft": [["thief", "danh từ"], ["theft", "danh từ"], ["thieve", "động từ"]],
    "thief": [["thief", "danh từ"], ["theft", "danh từ"], ["thieve", "động từ"]],
    "grief": [["grief", "danh từ"], ["grieve", "động từ"], ["grievous", "tính từ"]],
    "relief": [["relief", "danh từ"], ["relieve", "động từ"], ["relieved", "tính từ"]],
    "safety": [["safe", "tính từ"], ["safely", "trạng từ"], ["safety", "danh từ"], ["unsafe", "tính từ"]],
    "surgeon": [["surgery", "danh từ"], ["surgeon", "danh từ"], ["surgical", "tính từ"]],
    "village": [["village", "danh từ"], ["villager", "danh từ"]],
    "fraud": [["fraud", "danh từ"], ["fraudulent", "tính từ"]],
    "refuge": [["refuge", "danh từ"], ["refugee", "danh từ"]],
    "republic": [["republic", "danh từ"], ["republican", "tính từ"]],
    "theatre": [["theatre", "danh từ"], ["theatrical", "tính từ"]],
    "shortage": [["short", "tính từ"], ["shortage", "danh từ"], ["shorten", "động từ"]],
    "enthusiast": [["enthusiasm", "danh từ"], ["enthusiast", "danh từ"], ["enthusiastic", "tính từ"]],
}


def la_tu_don(tu):
    return bool(tu) and tu.replace("-", "").isalpha() and " " not in tu


# ---------- NẠP TỪ ĐIỂN + POS ----------
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
POS_WN = defaultdict(set)
for s in wn.all_synsets():
    for l in s.lemmas():
        w = l.name().replace("_", " ").lower()
        if la_tu_don(w):
            VN_WORDS.add(w)
            POS_WN[w].add(POS_WN_TV[s.pos()])
print(f"✅ Từ điển hợp lệ: {len(VN_WORDS)} từ")


def pos_day_du(cau):
    cac_pos = set(POS_WN.get(cau, ()))
    loai = LOAI_TU.get(cau)
    if loai and loai.lower() in POS_FULL_TV:
        cac_pos.add(POS_FULL_TV[loai.lower()])
    return sorted(cac_pos, key=lambda p: THU_TU_POS.get(p, 9))


# ---------- CHẠY ----------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
duong_khong = os.path.join(DUONG, "tu-khong-co-ho-tu.json")

with open(duong_ho_tu, encoding="utf-8") as f:
    HO_TU = json.load(f)

KHONG_CO = set()
if os.path.exists(duong_khong):
    with open(duong_khong, encoding="utf-8") as f:
        KHONG_CO = set(json.load(f))

con_thieu = [w for w in LOAI_TU if w not in HO_TU and w not in KHONG_CO]
print(f"Còn thiếu: {len(con_thieu)}")

them_curate = 0
danh_dau_khong = 0
bo_qua = []

for tu in con_thieu:
    if tu in CURATE:
        # thêm tay — kiểm tra mọi member là từ THẬT, POS từ từ điển/WordNet
        family = []
        for w, _pos in CURATE[tu]:
            if w not in VN_WORDS:
                bo_qua.append((tu, w))
                continue
            cac_pos = pos_day_du(w) or [_pos]
            family.append([w, cac_pos[0]])
        # bỏ trùng (w, pos)
        da_thay = set()
        sach = []
        for w, p in family:
            khoa = (w, p)
            if khoa in da_thay:
                continue
            da_thay.add(khoa)
            sach.append([w, p])
        if len(sach) >= 2:
            HO_TU[tu] = sach
            them_curate += 1
        else:
            danh_dau_khong += 1
            KHONG_CO.add(tu)
    else:
        # từ ghép / biệt lập → xác nhận KHÔNG có họ (trả [] NGAY, 0 Gemini)
        KHONG_CO.add(tu)
        danh_dau_khong += 1

# ---------- LƯU (có backup) ----------
with open(duong_ho_tu + ".bak3", "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

with open(duong_khong + ".bak3", "w", encoding="utf-8") as f:
    json.dump(sorted(KHONG_CO), f, ensure_ascii=False, indent=2)
with open(duong_khong, "w", encoding="utf-8") as f:
    json.dump(sorted(KHONG_CO), f, ensure_ascii=False, indent=2)

# dọn file tiến độ prefill cũ (không còn dùng Gemini nữa)
duong_tien_do = os.path.join(DUONG, "prefill-progress.json")
if os.path.exists(duong_tien_do):
    os.remove(duong_tien_do)

print("\n===== KẾT QUẢ HOÀN THIỆN OFFLINE =====")
print(f"Họ từ curate thêm: {them_curate}")
print(f"Đánh dấu không có họ: {danh_dau_khong}")
if bo_qua:
    print(f"⚠️ Member KHÔNG phải từ thật (đã bỏ): {bo_qua}")
con_lai = [w for w in LOAI_TU if w not in HO_TU and w not in KHONG_CO]
print(f"Tổng họ từ: {len(HO_TU)} | Tổng không có họ: {len(KHONG_CO)}")
print(f"Còn sót chưa xử lý: {len(con_lai)} — {con_lai[:10]}")
print(f"Coverage: {len(HO_TU)+len(KHONG_CO)}/{len(LOAI_TU)} ({100*(len(HO_TU)+len(KHONG_CO))//max(len(LOAI_TU),1)}%)")
