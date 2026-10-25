"""E19: goi y cho user co san, voi bo loc va mon bu (D14 d, D15)."""
import pytest

from api.dishes_common import DishFilter
from api.reasons import ALS

from .conftest import find_key

FILTERS = [
    {},
    {"veg": True},
    {"quick": True, "not_spicy": True},
    {"meal": "tối"},
    {"category": "canh/súp"},
    {"veg": True, "meal": "sáng", "category": "đồ uống"},   # rat hep: chac chan phai bu mon
]


def check_item_reason(x, user):
    src = x["source"]
    if src == "als":
        assert x["reason"] == ALS and x["dot"] == "herb"
    elif src == "content_slot":
        assert x["dot"] == "chili" and x["because"] and x["because"]["dish_name"]
        assert x["reason"] in (f"Giống món {x['because']['dish_name']} bạn đã nấu",
                               f"Giống món {x['because']['dish_name']} bạn đã xem")
    elif src == "pop":
        assert x["reason"] == f"Đang được nhiều người {user['age_group']} tuổi ở miền {user['region']} nấu"
    elif src == "fill":
        assert x["dot"] == "neutral" and x["reason"].endswith("được nấu nhiều trong danh mục")
        assert "vùng" not in x["reason"]
    elif src == "rep":
        assert x["reason"].startswith("Bạn đã nấu món này")


@pytest.mark.parametrize("flt", FILTERS, ids=lambda f: ",".join(f"{k}={v}" for k, v in f.items()) or "khong-loc")
def test_recs_invariants(client, db, sample_users, flt):
    f = DishFilter(**flt)
    n_catalog = db.dishes.count_documents(f.query())
    for uid in sample_users:
        r = client.get(f"/api/recs/{uid}", params=flt)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("truth", "nutrition", "score", "persona_main"):
            assert not find_key(body, k), f"user {uid} co khoa {k}"
        items = body["items"]
        rec = db.recs.find_one({"_id": uid})
        user = db.users.find_one({"_id": uid}, {"region": 1, "age_group": 1, "test_cooks": 1, "history": 1})
        rec_ids = [x["food_id"] for x in rec["items"]]
        hist = {h["food_id"] for h in user.get("history") or []}
        test_cooks = set(user.get("test_cooks") or [])
        ids = [x["food_id"] for x in items]
        assert len(ids) == len(set(ids)), "trung mon"
        if n_catalog >= 10 + len(rec_ids) + len(hist):
            assert len(items) == 10
        assert [x["rank"] for x in items] == list(range(1, len(items) + 1))
        # Moi mon deu thoa bo loc (doi chieu lai dishes)
        assert db.dishes.count_documents({"_id": {"$in": ids}, **f.query()}) == len(ids)
        from_recs = [x for x in items if x["source"] != "fill"]
        fills = [x for x in items if x["source"] == "fill"]
        # Mon tu goi y giu dung thu tu rank goc; mon bu luon dung sau
        assert [x["rec_rank"] for x in from_recs] == sorted(x["rec_rank"] for x in from_recs)
        assert items[:len(from_recs)] == from_recs
        assert all(x["food_id"] not in rec_ids and x["food_id"] not in hist for x in fills)
        for x in items:
            check_item_reason(x, user)
            assert x["hit"] == (x["food_id"] in test_cooks)
        s = body["summary"]
        assert s["from_recs"] == len(from_recs) and s["from_fill"] == len(fills)
        assert s["hits"] == sum(x["hit"] for x in items)
        if not flt:
            assert ids == rec_ids[:10], "khong loc thi phai dung 10 mon dau cua recs"


def test_narrow_filter_needs_fill(client, sample_users):
    body = client.get(f"/api/recs/{sample_users[0]}", params=FILTERS[-1]).json()
    assert body["summary"]["from_fill"] > 0
    fill = [x for x in body["items"] if x["source"] == "fill"]
    assert fill[0]["reason"] == "Món chay, bữa sáng, đồ uống được nấu nhiều trong danh mục"


def test_because_cooked_reason(client, db):
    # Tim 1 user co content_slot voi because_cooked = true va 1 user voi false
    for val, tail in ((True, "bạn đã nấu"), (False, "bạn đã xem")):
        doc = db.recs.find_one({"items": {"$elemMatch": {"source": "content_slot", "because_cooked": val, "rank": {"$lte": 10}}}})
        if doc is None:
            continue
        items = client.get(f"/api/recs/{doc['_id']}").json()["items"]
        x = next(i for i, r in zip(items, doc["items"]) if r["source"] == "content_slot" and r.get("because_cooked") is val)
        assert x["reason"].endswith(tail)


def test_recs_errors(client, sample_users):
    assert client.get("/api/recs/999999999").status_code == 404
    uid = sample_users[0]
    assert client.get(f"/api/recs/{uid}", params={"limit": 0}).status_code == 422
    assert client.get(f"/api/recs/{uid}", params={"limit": 21}).status_code == 422
    assert client.get(f"/api/recs/{uid}", params={"meal": "khuya"}).status_code == 422
    assert client.get(f"/api/recs/{uid}", params={"category": "không có"}).status_code == 422


def test_user_profile_has_no_truth(client, db, sample_users):
    for uid in sample_users[:10]:
        body = client.get(f"/api/users/{uid}").json()
        assert not find_key(body, "truth") and not find_key(body, "persona_main")
        assert body["user_id"] == uid
    assert client.get("/api/users/999999999").status_code == 404
