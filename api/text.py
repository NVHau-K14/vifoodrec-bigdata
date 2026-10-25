"""Chuan hoa chuoi tim mon giong het cot name_search cua buoc 07 (src/07_export_mongo.py).

Spark: trim(regexp_replace(translate(lower(dish_name), VN_FROM, VN_TO), "[^a-z0-9]+", " ")).
Them buoc NFC: mot so ban phim/trinh duyet gui chu dang to hop (NFD, "a" + dau rieng), translate() khong bat duoc.
"""
import re
import unicodedata

# Chep tu src/07_export_mongo.py (phai giong het, test_text.py kiem tra tren ca 5.499 mon)
VN_FROM = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")
VN_TO = ("aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd")
_TABLE = str.maketrans(VN_FROM, VN_TO)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_query(s):
    s = unicodedata.normalize("NFC", s).lower().translate(_TABLE)
    return _NON_ALNUM.sub(" ", s).strip()


def search_regex(s):
    """Chuoi da chuan hoa -> regex an toan cho $regex (khong de nguoi dung chen bieu thuc)."""
    return re.escape(normalize_query(s))
