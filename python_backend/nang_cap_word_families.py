# -*- coding: utf-8 -*-
"""
NÂNG CẤP word-families.json LÊN THUẬT TOÁN VÔ HƯỚNG (v2)
=========================================================
File hiện tại = 677 mục thủ công + 1738 mục sinh bởi bản WordNet v1 (bắc cầu 1 chiều).
Bản v1 có "chữ ký" rõ ràng: member ĐẦU TIÊN luôn là chính từ đang tra + sắp theo bảng chữ cái.
Script này:
  1. Tái lập ĐÚNG đầu ra v1 cho từng từ -> so khớp với file hiện tại.
     - Khớp    -> đó là mục v1 (không phải 677 thủ công) -> nâng cấp bằng v2 (vô hướng).
     - Không   -> đó là mục thủ công (chất lượng cao)    -> GIỮ NGUYÊN.
  2. Bổ sung thêm các từ còn thiếu hoàn toàn bằng v2.
"""
import json
import os
from collections import defaultdict, OrderedDict

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


# ---------- NẠP TỪ ĐIỂN ----------
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


# ---------- TÁI LẬP ĐÚNG THUẬT TOÁN v1 (để nhận diện mục v1) ----------
def v1_hang_xom(u):
    """BFS bắc cầu 1 chiều kiểu v1: trả về dict word -> set(pos)."""
    family = {}
    queue = [u]
    seen = {u}
    while queue:
        w = queue.pop(0)
        for s in wn.synsets(w):
            for l in s.lemmas():
                ten = l.name().replace("_", " ")
                if ten != w:
                    continue
                pos = POS_WN_TV.get(l.synset().pos(), "")
                if la_tu_don(ten):
                    family.setdefault(ten, set()).add(pos)
                for quan_he in (l.derivationally_related_forms(), l.pertainyms(),
                                [a for a in l.antonyms() if la_phu_dinh(a.name().replace("_", " "), ten)]):
                    for r in quan_he:
                        ten_r = r.name().replace("_", " ")
                        if not la_tu_don(ten_r):
                            continue
                        pos_r = POS_WN_TV.get(r.synset().pos(), "")
                        if ten_r not in seen:
                            seen.add(ten_r)
                            queue.append(ten_r)
                        family.setdefault(ten_r, set()).add(pos_r)
    return family


def v1_gom(u):
    thien = v1_hang_xom(u)
    ket = OrderedDict()
    ket[u] = pos_tv_cho(u, thien.get(u, set()))
    for m, cac_pos in sorted(thien.items()):
        if m == u or m not in TU_VUNG or m in ket:
            continue
        ket[m] = pos_tv_cho(m, cac_pos)
    return [[w, p] for w, p in ket.items() if w]


def pos_tv_cho(u, cac_pos_wn):
    loai = LOAI_TU.get(u)
    if loai:
        return POS_FULL_TV.get(loai.lower(), loai)
    for p in sorted(cac_pos_wn):
        if p:
            return p
    return ""


# ---------- THUẬT TOÁN v2 (vô hướng) ----------
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


def v2_gom(u):
    gia = set()
    hang_doi, da_gap = [u], {u}
    while hang_doi:
        w = hang_doi.pop(0)
        gia.add(w)
        for v in ADJ.get(w, ()):
            if v not in da_gap:
                da_gap.add(v)
                hang_doi.append(v)
    if len(gia) < 2:
        return []
    cac_dong = []
    for w in sorted(gia):
        loai = LOAI_TU.get(w)
        if loai:
            cac_pos = [POS_FULL_TV.get(loai.lower(), loai)]
        else:
            cac_pos = sorted({POS_WN_TV.get(s.pos(), "") for s in wn.synsets(w)}) or [""]
        for p in cac_pos:
            cac_dong.append([w, p])
    cac_dong.sort(key=lambda d: (THU_TU_POS.get(d[1], 9), d[0]))
    da_thay = {w for w, _ in cac_dong[:CAP_HO]}
    if u not in da_thay:
        loai = LOAI_TU.get(u)
        cac_dong.insert(0, [u, POS_FULL_TV.get(loai.lower(), loai) if loai else ""])
    return cac_dong[:CAP_HO]


# ---------- CHẠY NÂNG CẤP ----------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
with open(duong_ho_tu, encoding="utf-8") as f:
    HO_TU = json.load(f)

print(f"File hiện tại: {len(HO_TU)} mục")

gio_thu_cong = 0      # mục giữ nguyên (677 thủ công + mục khớp trùng ngẫu nhiên)
len_thanh_v1 = 0      # mục v1 phát hiện -> nâng cấp v2
them_moi = 0          # từ mới bổ sung
thieu = 0

cac_tu_chinh = sorted(LOAI_TU.keys())
for i, tu in enumerate(cac_tu_chinh, 1):
    if tu not in HO_TU:
        family = v2_gom(tu)
        if family:
            HO_TU[tu] = family
            them_moi += 1
        else:
            thieu += 1
        continue
    # So khớp chữ ký v1: nếu mục đang lưu ĐÚNG BẰNG đầu ra v1 -> là mục v1 -> nâng cấp v2
    if HO_TU[tu] == v1_gom(tu):
        family = v2_gom(tu)
        if family:
            HO_TU[tu] = family
            len_thanh_v1 += 1
        else:
            thieu += 1
    else:
        gio_thu_cong += 1
    if i % 500 == 0:
        print(f"  ...{i}/{len(cac_tu_chinh)} (giữ {gio_thu_cong}, nâng cấp {len_thanh_v1}, thêm mới {them_moi}, thiếu {thieu})")

# Backup trước khi ghi
with open(duong_ho_tu + ".bak", "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

tong_member = sum(len(v) for v in HO_TU.values())
print("\n===== KẾT QUẢ NÂNG CẤP =====")
print(f"Tổng headword: {len(HO_TU)} / {len(cac_tu_chinh)} ({len(HO_TU)*100//len(cac_tu_chinh)}%)")
print(f"Giữ nguyên (thủ công): {gio_thu_cong} | Nâng cấp v1->v2: {len_thanh_v1} | Thêm mới: {them_moi} | Thiếu: {thieu}")
print(f"Tổng member: {tong_member} | Trung bình: {round(tong_member/len(HO_TU), 2)}")
