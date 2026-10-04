# -*- coding: utf-8 -*-
"""
BỔ SUNG HỌ TỪ OFFLINE (KHÔNG GỌI GEMINI) — CHỈ THÊM TỪ CÒN THIẾU
==================================================================
Nguyên tắc AN TOÀN TUYỆT ĐỐI:
  - KHÔNG đụng 1 chữ nào vào 2.578 mục đang chạy ổn định (677 thủ công + WordNet).
  - CHỈ tạo mục MỚI cho các từ còn thiếu trong word-families.json.
  - Nguồn dữ liệu 100% offline (nhanh, không lỗi mạng, không tốn API):
      1) WordNet đồ thị vô hướng (v2)
      2) word_forms — database biến đổi từ đã được tuyển chọn
  - Lọc NGHIÊM: mọi member phải nằm trong từ điển của app (full-word.json / CEFR CSV),
    đảm bảo front-end luôn có IPA + nghĩa để hiển thị.
"""
import json
import os
from collections import defaultdict

from nltk.corpus import wordnet as wn
from word_forms.word_forms import get_word_forms

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
WF_POS = {'n': 'danh từ', 'v': 'động từ', 'a': 'tính từ', 'r': 'trạng từ'}
NEG_PREFIX = ("un", "in", "im", "il", "ir", "dis", "non", "mis", "de", "ab")
THU_TU_POS = {"danh từ": 0, "động từ": 1, "tính từ": 2, "trạng từ": 3}
CAP_HO = 12


def la_tu_don(tu):
    return bool(tu) and tu.replace("-", "").isalpha() and " " not in tu


def la_phu_dinh(member, goc):
    goc, member = goc.lower(), member.lower()
    for p in NEG_PREFIX:
        if member.startswith(p) and member[len(p):] == goc:
            return True
    return False


# ---------- NẠP TỪ ĐIỂN (chỉ đọc, không sửa) ----------
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


def pos_tu_dien(u):
    """POS tiếng Việt từ từ điển app (ưu tiên tuyệt đối)."""
    loai = LOAI_TU.get(u)
    if loai:
        return POS_FULL_TV.get(loai.lower(), loai)
    return ""


# ---------- NGUỒN 1: WORDNET ĐỒ THỊ VÔ HƯỚNG (v2) ----------
def hang_xom(u):
    cac_hang = set()
    for s in wn.synsets(u):
        for l in s.lemmas():
            if l.name().replace("_", " ") != u:
                continue
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


ADJ = defaultdict(set)
for w in TU_VUNG:
    for v in hang_xom(w):
        if v in TU_VUNG and v != w:
            ADJ[w].add(v)
            ADJ[v].add(w)


def ho_wordnet_v2(u):
    """Họ từ theo WordNet v2 — trả về dict word -> set(POS)."""
    gia = set()
    hang_doi, da_gap = [u], {u}
    while hang_doi:
        w = hang_doi.pop(0)
        gia.add(w)
        for v in ADJ.get(w, ()):
            if v not in da_gap:
                da_gap.add(v)
                hang_doi.append(v)
    ket = {}
    for w in gia:
        if not pos_tu_dien(w):
            ket.setdefault(w, set()).update(POS_WN_TV.get(s.pos(), "") for s in wn.synsets(w))
    return ket


# ---------- NGUỒN 2: WORD_FORMS (database biến đổi từ tuyển chọn) ----------
def ho_word_forms(u):
    """Họ từ theo word_forms — trả về dict word -> set(POS). Lọc theo từ điển app."""
    ket = defaultdict(set)
    try:
        for cat, cac_tu in get_word_forms(u).items():
            pos = WF_POS.get(cat)
            if not pos:
                continue
            for w in cac_tu:
                if w in TU_VUNG:
                    ket[w].add(pos)
    except Exception:
        pass
    return dict(ket)


# ---------- GỘP HAI NGUỒN ----------
def ho_offline(u):
    """Họ từ offline tổng hợp (WordNet v2 + word_forms), lọc từ điển app."""
    gop = defaultdict(set)
    for w, cac_pos in ho_wordnet_v2(u).items():
        gop[w].update(cac_pos)
    for w, cac_pos in ho_word_forms(u).items():
        gop[w].update(cac_pos)
    if not gop:
        return []
    cac_dong = []
    da_thay = set()
    for w in sorted(gop):
        if w not in TU_VUNG or w in da_thay:
            continue
        da_thay.add(w)
        cac_pos = gop[w] or {""}
        # Ưu tiên POS từ điển app, thêm các POS khác của WordNet/word_forms
        pos_dd = pos_tu_dien(w)
        cac_pos_dong = set(cac_pos)
        if pos_dd:
            cac_pos_dong.add(pos_dd)
        for p in sorted(cac_pos_dong):
            cac_dong.append([w, p])
    cac_dong.sort(key=lambda d: (THU_TU_POS.get(d[1], 9), d[0]))
    da_thay = {w for w, _ in cac_dong[:CAP_HO]}
    if u not in da_thay:
        cac_dong.insert(0, [u, pos_tu_dien(u) or next((p for _, p in cac_dong), "")])
    return cac_dong[:CAP_HO]


# ---------- CHẠY BỔ SUNG ----------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
with open(duong_ho_tu, encoding="utf-8") as f:
    HO_TU = json.load(f)

print(f"Mục đang có: {len(HO_TU)} (GIỮ NGUYÊN, không đụng tới)")

cac_tu_chinh = sorted(LOAI_TU.keys())
them_moi = 0
thieu = 0
for i, tu in enumerate(cac_tu_chinh, 1):
    if tu in HO_TU:
        continue  # ⛔ tuyệt đối không đụng mục đã có
    family = ho_offline(tu)
    if family:
        HO_TU[tu] = family
        them_moi += 1
    else:
        thieu += 1
    if i % 1000 == 0:
        print(f"  ...{i}/{len(cac_tu_chinh)} (thêm mới {them_moi}, còn thiếu {thieu})")

# Backup + ghi (chỉ THÊM, không xoá gì)
with open(duong_ho_tu + ".bak2", "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

tong_member = sum(len(v) for v in HO_TU.values())
print("\n===== KẾT QUẢ BỔ SUNG OFFLINE =====")
print(f"Tổng headword: {len(HO_TU)} / {len(cac_tu_chinh)} ({len(HO_TU)*100//len(cac_tu_chinh)}%)")
print(f"Thêm mới offline: {them_moi} | Còn thiếu (sẽ rơi vào Gemini fallback): {thieu}")
print(f"Tổng member: {tong_member} | Trung bình: {round(tong_member/len(HO_TU), 2)}")
