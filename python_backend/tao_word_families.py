# -*- coding: utf-8 -*-
"""
TẠO word-families.json TỰ ĐỘNG BẰNG WORDNET (phương án A)
=========================================================
Sinh họ từ (word family) cho TOÀN BỘ từ trong full-word.json dựa trên:
  1. WordNet: synset + derivationally_related_forms + pertainym + antonym (tiền tố phủ định)
  2. BFS bắc cầu qua các quan hệ trên để gom đủ biến thể cùng gốc
  3. BỘ LỌC: chỉ giữ member nằm trong từ điển app (full-word.json + CEFR CSV)
     -> tooltip luôn hiện được IPA/nghĩa/cấp độ cho TỪNG member.
  4. GIỮ NGUYÊN 677 mục biên soạn thủ công hiện có (chất lượng cao hơn, ưu tiên override).

Chạy:  python3 tao_word_families.py
"""
import json
import os
from collections import defaultdict, OrderedDict

from nltk.corpus import wordnet as wn

DUONG = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# BẢNG MAP TỪ LOẠI
# ---------------------------------------------------------------------------
POS_WN_TV = {   # WordNet pos -> tiếng Việt
    'n': 'danh từ',
    'v': 'động từ',
    'a': 'tính từ',
    's': 'tính từ',   # adjective satellite
    'r': 'trạng từ',
}

POS_FULL_TV = {  # full-word.json "type" -> tiếng Việt (đồng bộ main.py)
    "noun": "danh từ", "verb": "động từ", "adjective": "tính từ",
    "adverb": "trạng từ", "pronoun": "đại từ", "preposition": "giới từ",
    "determiner": "từ hạn định", "number": "số từ", "conjunction": "liên từ",
    "exclamation": "thán từ", "modal verb": "trợ động từ tình thái",
    "ordinal number": "số thứ tự", "auxiliary verb": "trợ động từ",
    "indefinite article": "mạo từ không xác định", "linking verb": "động từ nối",
    "definite article": "mạo từ xác định", "infinitive marker": "tiểu từ nguyên mẫu",
}

# Tiền tố phủ định — chỉ nhận antonym có dạng "tiền tố + chính từ đó"
# (vd successful->unsuccessful, capable->incapable, happy->unhappy).
# Từ đó loại bỏ antonym KHÔNG cùng họ (vd happy->sad, succeed->fail).
NEG_PREFIX = ("un", "in", "im", "il", "ir", "dis", "non", "mis", "de", "ab")


def la_tu_don(tu):
    """Chỉ giữ từ đơn (bỏ 'bring home the bacon', 'well-chosen', số...)."""
    return bool(tu) and tu.replace("-", "").isalpha() and " " not in tu


def la_phu_dinh(member, goc):
    """Antonym có phải là 'tiền tố phủ định + từ gốc' không (vd unsuccessful/successful)."""
    goc = goc.lower()
    member = member.lower()
    for p in NEG_PREFIX:
        if member == p + goc:
            return True
        # Biến thể ghép vần đơn giản (vd able->unable, irregular->irregular là chính nó)
        if member.startswith(p) and member[len(p):] == goc:
            return True
    return False


# ---------------------------------------------------------------------------
# 1) NẠP TỪ ĐIỂN APP LÀM "BỘ LỌC" (chỉ giữ member quen thuộc)
# ---------------------------------------------------------------------------
TU_VUNG = set()  # các từ app hiển thị được (có IPA/nghĩa/level)
LOAI_TU = {}     # từ -> type tiếng Anh (noun/verb...) lấy từ full-word.json

with open(os.path.join(DUONG, "full-word.json"), encoding="utf-8") as f:
    for item in json.load(f):
        val = item.get("value", {})
        w = (val.get("word") or "").strip().lower()
        if w:
            TU_VUNG.add(w)
            t = (val.get("type") or "").strip()
            if t:
                LOAI_TU[w] = t

# CEFR CSV (bảng 9.936 từ) — thêm vào bộ lọc để giữ thêm member A1/A2
duong_csv = os.path.join(DUONG, "..", "..", "ENGLISH_CERF_WORDS.csv")
if os.path.exists(duong_csv):
    with open(duong_csv, encoding="utf-8") as f:
        next(f, None)
        for dong in f:
            dong = dong.strip()
            if not dong:
                continue
            phan = dong.rsplit(",", 1)
            if len(phan) != 2:
                continue
            for bien_the in phan[0].strip().lower().split("/"):
                if bien_the:
                    TU_VUNG.add(bien_the)

print(f"Bộ lọc từ điển app: {len(TU_VUNG)} từ")

# ---------------------------------------------------------------------------
# 2) DỰNG ĐỒ THỊ VÔ HƯỚNG + BFS
#    WordNet coi quan hệ DRF/pertainym là 1 CHIỀU (vd accurate->accuracy có cạnh,
#    accuracy->accurate thì không). Xây đồ thị vô hướng nên bắt được ở CẢ 2 phía.
# ---------------------------------------------------------------------------


def hang_xom(u):
    """Các từ WordNet coi là có quan hệ với u (DRF + pertainym + antonym phủ định)."""
    cac_hang = set()
    for s in wn.synsets(u):
        for l in s.lemmas():
            if l.name().replace("_", " ") != u:
                continue  # chỉ đi từ lemma đúng bằng từ đang xét (không lẫn từ đồng nghĩa)
            for r in l.derivationally_related_forms():
                ten = r.name().replace("_", " ")
                if la_tu_don(ten):
                    cac_hang.add(ten)
            for p in l.pertainyms():
                ten = p.name().replace("_", " ")
                if la_tu_don(ten):
                    cac_hang.add(ten)
            for a in l.antonyms():
                ten = a.name().replace("_", " ")
                if la_tu_don(ten) and la_phu_dinh(ten, u):
                    cac_hang.add(ten)
    return cac_hang


ADJ = defaultdict(set)  # đồ thị vô hướng: từ -> set các từ cùng họ
for w in TU_VUNG:
    for v in hang_xom(w):
        if v in TU_VUNG and v != w:
            ADJ[w].add(v)
            ADJ[v].add(w)  # vô hướng
print(f"Đồ thị vô hướng: {len(ADJ)} đỉnh có ít nhất 1 cạnh")


THU_TU_POS = {"danh từ": 0, "động từ": 1, "tính từ": 2, "trạng từ": 3}
CAP_HO = 12  # giới hạn member 1 họ (tránh cụm quá lớn)


def gia_dinh_wordnet(tu):
    """BFS qua đồ thị vô hướng -> set các từ cùng họ với `tu`."""
    gia = set()
    hang_doi = [tu]
    da_gap = {tu}
    while hang_doi:
        u = hang_doi.pop(0)
        gia.add(u)
        for v in ADJ.get(u, ()):
            if v not in da_gap:
                da_gap.add(v)
                hang_doi.append(v)
    return gia


def pos_cua(tu):
    """POS tiếng Việt: full-word.json -> WordNet -> rỗng."""
    loai = LOAI_TU.get(tu)
    if loai:
        return [POS_FULL_TV.get(loai.lower(), loai)]
    cac_pos = set()
    for s in wn.synsets(tu):
        p = POS_WN_TV.get(s.pos(), "")
        if p:
            cac_pos.add(p)
    return sorted(cac_pos) or [""]


def gom_gia_dinh(tu):
    """Họ từ [[word, pos], ...] sắp theo (POS, từ) — đúng kiểu biên soạn thủ công."""
    cac_tu = gia_dinh_wordnet(tu)
    if len(cac_tu) < 2:
        return []
    # Member có nhiều POS -> tách thành nhiều dòng (giống 'relative' danh từ + tính từ)
    cac_dong = []
    for w in sorted(cac_tu):
        for p in pos_cua(w):
            cac_dong.append([w, p])
    cac_dong.sort(key=lambda d: (THU_TU_POS.get(d[1], 9), d[0]))
    # Luôn đảm bảo có chính từ đang tra (nếu lỡ bị cap cắt mất)
    da_thay = {w for w, _ in cac_dong[:CAP_HO]}
    if tu not in da_thay:
        cac_dong.insert(0, [tu, pos_cua(tu)[0]])
    return cac_dong[:CAP_HO]


# ---------------------------------------------------------------------------
# 3) NẠP 677 MỤC THỦ CÔNG + SINH PHẦN CÒN THIẾU
# ---------------------------------------------------------------------------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
HO_TU = {}
if os.path.exists(duong_ho_tu):
    with open(duong_ho_tu, encoding="utf-8") as f:
        HO_TU = json.load(f)
print(f"Đã nạp {len(HO_TU)} mục thủ công (giữ nguyên làm override).")

# Danh sách headword cần phủ = toàn bộ từ trong full-word.json
cac_tu_chinh = sorted(LOAI_TU.keys())

them_moi = 0
khong_tim_thay = 0
for i, tu in enumerate(cac_tu_chinh, 1):
    if tu in HO_TU:
        continue
    family = gom_gia_dinh(tu)
    if len(family) >= 2:
        HO_TU[tu] = family
        them_moi += 1
    else:
        khong_tim_thay += 1
    if i % 500 == 0:
        print(f"  ...đã xử lý {i}/{len(cac_tu_chinh)} (thêm mới {them_moi}, không tìm thấy {khong_tim_thay})")

# ---------------------------------------------------------------------------
# 4) GHI FILE + THỐNG KÊ
# ---------------------------------------------------------------------------
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

tong_member = sum(len(v) for v in HO_TU.values())
co_pos = sum(1 for v in HO_TU.values() for m in v if len(m) == 2 and m[1])
print("\n===== KẾT QUẢ =====")
print(f"Tổng headword: {len(HO_TU)} / {len(cac_tu_chinh)} ({len(HO_TU)*100//len(cac_tu_chinh)}%)")
print(f"Thêm mới (WordNet): {them_moi} | Không tìm thấy (sẽ nhờ Gemini khi tra): {khong_tim_thay}")
print(f"Tổng member: {tong_member} | Có POS tiếng Việt: {co_pos} ({co_pos*100//max(tong_member,1)}%)")
print(f"Trung bình thành viên/họ: {round(tong_member/len(HO_TU), 2)}")
print(f"\nĐã lưu: {duong_ho_tu}")
