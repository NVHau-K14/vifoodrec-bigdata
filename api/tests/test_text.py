"""Chuan hoa chuoi tim mon phai giong het cot name_search cua buoc 07."""
import unicodedata

from api.text import normalize_query


def test_normalize_matches_name_search_all_dishes(db):
    bad = [(d["_id"], d["dish_name"], d["name_search"]) for d in db.dishes.find({}, {"dish_name": 1, "name_search": 1})
           if normalize_query(d["dish_name"]) != d["name_search"]]
    assert db.dishes.estimated_document_count() > 0
    assert bad == []


def test_normalize_cases():
    assert normalize_query("Đậu Hũ") == "dau hu"
    assert normalize_query("  canh   chua!! ") == "canh chua"
    # Chu to hop (NFD) phai ra cung ket qua voi chu dung san (NFC)
    assert normalize_query(unicodedata.normalize("NFD", "Bún bò Huế")) == "bun bo hue"
    assert normalize_query("(.*)") == ""


def test_search_with_and_without_accents(client):
    a = client.get("/api/dishes/search", params={"q": "đậu hũ"}).json()
    b = client.get("/api/dishes/search", params={"q": "dau hu"}).json()
    nfd = client.get("/api/dishes/search", params={"q": unicodedata.normalize("NFD", "đậu hũ")}).json()
    assert a and a == b == nfd
    assert all("dau hu" in normalize_query(x["dish_name"]) for x in a)


def test_search_regex_is_escaped(client):
    r = client.get("/api/dishes/search", params={"q": "a.*b"})
    assert r.status_code == 200
    # ".*" la ky tu thuong sau khi chuan hoa -> "a b", khong phai bieu thuc chon moi mon
    assert all("a b" in normalize_query(x["dish_name"]) for x in r.json())


def test_search_validation(client):
    assert client.get("/api/dishes/search", params={"q": "a"}).status_code == 422
    assert client.get("/api/dishes/search", params={"q": "!!"}).json() == []
