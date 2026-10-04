# -*- coding: utf-8 -*-
"""
NÂNG CẤP HỌ TỪ OFFLINE LẦN 2 — THÊM LUẬT CẤU TẠO TỪ (MORPHOLOGY RULES)
====================================================================
Vấn đề lần 1: lọc theo "có trong từ điển app" quá chặt → nhiều mục chỉ còn 1 từ
(vd accuracy → [accuracy]) vô dụng và còn CHẶN cả Gemini fallback.

Giải pháp:
  - Thêm 3 nguồn offline: WordNet v2 + word_forms + LUẬT SUFFIX (accuracy→accurate,
    abortion→abort, abolish→abolition...) + biến thể phủ định (in-/un-...).
  - Bộ lọc mới: từ phải là từ THẬT = nằm trong từ điển app HOẶC có trong WordNet
    (từ điển 155k từ chuẩn) → đủ rộng để nhận accurate/abort, đủ chặt để chặn rác.
  - CHỈ thay thế các mục CÓ 1 TỪ (vô dụng) và thêm mục CÒN THIẾU.
    ⛔ KHÔNG đụng 2.578 mục đang chạy ổn định (677 thủ công + WordNet v2).
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
NEG_PREFIX = ("un", "in", "im", "il", "ir", "dis", "non", "mis")
THU_TU_POS = {"danh từ": 0, "động từ": 1, "tính từ": 2, "trạng từ": 3}
CAP_HO = 12

# (strip, add): bỏ `strip` ở đuôi từ, thêm `add`
# Thứ tự: càng đặc thù càng trước để ưu tiên khớp đúng (vd acy→ate trước ate→...)
LUAT_SUFFIX = [
    # danh từ ↔ tính từ / trạng từ (accuracy/accurate/accurately)
    ("acy", "ate"), ("acy", "ately"),
    # -tion/-sion ↔ động từ (relation/relate, decision/decide)
    ("tion", "te"), ("tion", "tive"), ("tion", "tional"), ("tion", "ally"),
    ("sion", "de"), ("sive", "sion"), ("sive", "sively"),
    ("e", "ion"), ("e", "ive"), ("e", "ation"), ("", "ion"),
    # danh từ → động từ
    ("ment", ""), ("ment", "mental"), ("th", ""), ("ure", ""),
    ("age", "e"), ("ance", ""), ("ence", ""), ("ness", ""), ("ness", "ly"),
    ("", "ment"), ("", "ance"), ("", "ence"), ("", "age"), ("", "ure"), ("", "th"),
    # tính từ ↔ danh từ/động từ
    ("ful", ""), ("less", ""), ("ous", ""), ("able", ""), ("ible", ""),
    ("al", ""), ("al", "e"), ("al", "ly"), ("ic", "y"), ("ish", ""),
    ("ent", ""), ("ent", "ently"), ("ant", ""), ("y", ""), ("y", "ily"),
    ("", "ful"), ("", "less"), ("", "ous"), ("", "able"), ("", "ive"),
    ("", "al"), ("", "ent"), ("", "ant"),
    # danh từ chỉ người / trừu tượng
    ("er", ""), ("or", ""), ("ist", ""), ("ist", "ce"), ("ism", ""),
    ("ship", ""), ("hood", ""), ("", "er"), ("", "or"), ("", "ist"),
    ("", "ism"), ("", "ship"), ("", "hood"),
    # động từ → động từ / tính từ khác
    ("ize", ""), ("ify", ""), ("ify", "ication"), ("en", ""), ("", "ize"),
    ("", "ify"), ("", "en"), ("ation", "e"),
    # luật đặc thù: advice/advise, anxiety/anxious, allegation/allege, actress/actor
    ("ice", "ise"), ("ise", "ice"), ("iety", "ious"), ("ous", "iety"),
    ("ous", "ously"), ("ous", "ousness"), ("ess", "or"), ("", "ess"),
    ("ress", "or"), ("ess", "e"),
    ("ent", "ence"), ("ent", "ency"), ("ant", "ance"),
    ("ive", "ity"), ("ity", "e"), ("ive", "ively"),
    ("ible", "ibility"), ("ibility", "ible"),
    # biến thể hình thái (inflection)
    ("ed", ""), ("ing", ""), ("e", "ed"), ("e", "ing"), ("e", "able"),
    ("y", "ier"), ("y", "iest"), ("y", "iness"),
    ("", "ly"), ("", "er"), ("", "ed"), ("", "ing"),
    # trạng từ → gốc (basically→basic, normally→normal, easily→easy)
    # guard len>=4 để chặn false-positive: early→ear, imply→imp, finally→fin
    ("ally", ""), ("ly", ""), ("ily", "y"),
]
# POS mặc định theo kiểu suffix (chỉ dùng khi từ điển + WordNet không xác định được)
POS_SUFFIX = {
    "ate": "tính từ", "ately": "trạng từ", "ly": "trạng từ", "ily": "trạng từ",
    "ent": "tính từ", "ant": "tính từ", "al": "tính từ", "ful": "tính từ",
    "less": "tính từ", "ous": "tính từ", "able": "tính từ", "ible": "tính từ",
    "ive": "tính từ", "ic": "tính từ", "ish": "tính từ", "tive": "tính từ",
    "tional": "tính từ", "mental": "tính từ", "ed": "tính từ", "ing": "tính từ",
    "ion": "danh từ", "tion": "danh từ", "sion": "danh từ", "ment": "danh từ",
    "ness": "danh từ", "th": "danh từ", "ure": "danh từ", "age": "danh từ",
    "ance": "danh từ", "ence": "danh từ", "er": "danh từ", "or": "danh từ",
    "ist": "danh từ", "ism": "danh từ", "ship": "danh từ", "hood": "danh từ",
    "ication": "danh từ", "ation": "danh từ", "iness": "danh từ",
    "ize": "động từ", "ify": "động từ", "en": "động từ", "ate_v": "động từ",
    "de": "động từ", "te": "động từ", "e": "động từ",
}


def la_tu_don(tu):
    return bool(tu) and tu.replace("-", "").isalpha() and " " not in tu


def pos_theo_duoi(cau):
    """Đoán POS theo đuôi từ (dự phòng) — chỉ là cú pháp, không phải ý nghĩa."""
    for duoi, pos in sorted(POS_SUFFIX.items(), key=lambda x: -len(x[0])):
        if cau.endswith(duoi) and len(cau) > len(duoi):
            return pos
    return ""


# ---------- NẠP TỪ ĐIỂN APP ----------
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
    loai = LOAI_TU.get(u)
    if loai:
        return POS_FULL_TV.get(loai.lower(), loai)
    return ""


# ---------- TỪ ĐIỂN WORDNET (một lần, dùng cho lọc + POS) ----------
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
    """POS đầy đủ: từ điển app → WordNet → đoán theo đuôi."""
    cac_pos = set(POS_WN.get(cau, ()))
    p = pos_tu_dien(cau)
    if p:
        cac_pos.add(p)
    if not cac_pos:
        p = pos_theo_duoi(cau)
        if p:
            cac_pos.add(p)
    return cac_pos


# ---------- NGUỒN 1: WORDNET ĐỒ THỊ VÔ HƯỚNG ----------
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
    return cac_hang


ADJ = defaultdict(set)
for w in TU_VUNG:
    for v in hang_xom(w):
        if v in VN_WORDS and v != w:
            ADJ[w].add(v)
            ADJ[v].add(w)


def ho_wordnet_v2(u):
    gia = set()
    hang_doi, da_gap = [u], {u}
    while hang_doi:
        w = hang_doi.pop(0)
        gia.add(w)
        for v in ADJ.get(w, ()):
            if v not in da_gap:
                da_gap.add(v)
                hang_doi.append(v)
    return gia


# ---------- NGUỒN 2: WORD_FORMS ----------
def ho_word_forms(u):
    ket = set()
    try:
        for cac_tu in get_word_forms(u).values():
            for w in cac_tu:
                if w in VN_WORDS:
                    ket.add(w)
    except Exception:
        pass
    return ket


# ---------- NGUỒN 3: LUẬT SUFFIX + PHỦ ĐỊNH ----------
def sinh_cau_tu(u):
    """Sinh các dạng biến thể bằng luật suffix + tiền tố phủ định."""
    cac_cau = set()
    for strip_s, add_s in LUAT_SUFFIX:
        if strip_s:
            if not u.endswith(strip_s) or len(u) <= len(strip_s) + 1:
                continue
            goc = u[:-len(strip_s)]
        else:
            goc = u
        cau = goc + add_s
        # chặn false-positive của luật bỏ đuôi -ly/-ally/-ily (early→ear, finally→fin)
        if strip_s in ("ly", "ally", "ily") and len(cau) < 4:
            continue
        if cau == u or not la_tu_don(cau):
            continue
        cac_cau.add(cau)
        # xử lý i↔y (happiness → happy, happily)
        if cau.endswith("i") and len(cau) > 1:
            cac_cau.add(cau[:-1] + "y")
        # e-drop ngược (nature → natural đã có qua luật al; tạo thêm natur+e)
        if add_s == "" and cau.endswith("r") and (cau + "e") != u:
            cac_cau.add(cau + "e")
    # biến thể phủ định: gốc → un-/in-...
    for m in list(cac_cau) + [u]:
        for p in NEG_PREFIX:
            cau2 = p + m
            if cau2 != u and la_tu_don(cau2) and cau2 in VN_WORDS:
                cac_cau.add(cau2)
    return cac_cau


# ---------- GỘP TOÀN BỘ ----------
def ho_offline(u):
    cac_tu = {u}
    cac_tu.update(ho_wordnet_v2(u))
    cac_tu.update(ho_word_forms(u))
    cac_tu.update(sinh_cau_tu(u))
    gop = defaultdict(set)
    for w in cac_tu:
        if w not in VN_WORDS:
            continue
        for p in pos_day_du(w):
            gop[w].add(p)
        if w in (u,) and not gop[w]:
            gop[w].add("")
    cac_dong = []
    da_thay = set()
    for w in sorted(gop):
        if w in da_thay:
            continue
        da_thay.add(w)
        cac_pos = sorted(gop[w] or {""})
        for p in cac_pos:
            cac_dong.append([w, p])
    cac_dong.sort(key=lambda d: (THU_TU_POS.get(d[1], 9), d[0]))
    da_thay = {w for w, _ in cac_dong[:CAP_HO]}
    if u not in da_thay:
        cac_dong.insert(0, [u, pos_tu_dien(u) or (next((p for _, p in cac_dong), ""))])
    return cac_dong[:CAP_HO]


# ---------- CHẠY ----------
duong_ho_tu = os.path.join(DUONG, "word-families.json")
with open(duong_ho_tu, encoding="utf-8") as f:
    HO_TU = json.load(f)

truoc = len(HO_TU)
thay_1tu = 0
them_moi = 0
da_thay = set()
for tu in sorted(LOAI_TU.keys()):
    # 1) Mục đang có từ 2 member trở lên → GIỮ NGUYÊN tuyệt đối
    hien_tai = HO_TU.get(tu)
    if hien_tai and len(hien_tai) > 1:
        continue
    # 2) Mục 1 từ (rác của lần chạy trước) hoặc chưa có → thay/thêm bằng họ offline đầy đủ
    family = ho_offline(tu)
    if len(family) >= 2:
        if hien_tai:
            thay_1tu += 1
        else:
            them_moi += 1
        HO_TU[tu] = family
        da_thay.add(tu)
    elif len(family) == 1:
        # không cứu được → XÓA mục 1 từ để Gemini fallback được gọi (không chặn nữa)
        if hien_tai:
            del HO_TU[tu]
            thay_1tu += 1

with open(duong_ho_tu + ".bak2", "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)
with open(duong_ho_tu, "w", encoding="utf-8") as f:
    json.dump(HO_TU, f, ensure_ascii=False, indent=2)

print("\n===== KẾT QUẢ NÂNG CẤP OFFLINE (LẦN 2) =====")
print(f"Mục ban đầu: {truoc} → sau: {len(HO_TU)}")
print(f"Thay mục 1-từ bằng họ đầy đủ: {thay_1tu}")
print(f"Thêm mới (còn thiếu trước đó): {them_moi}")
tong_member = sum(len(v) for v in HO_TU.values())
print(f"Coverage: {len(HO_TU)} / {len(LOAI_TU)} ({len(HO_TU)*100//len(LOAI_TU)}%)")
print(f"Tổng member: {tong_member} | TB: {round(tong_member/len(HO_TU), 2)}")
