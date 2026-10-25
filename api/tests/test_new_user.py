"""E20: goi y cho user moi tu cac mon da chon (content), bu bang popular roi bu tu danh muc."""
from api.dishes_common import DishFilter

from .conftest import by_hash, find_key


def chosen_sets(db):
    ids = [d["_id"] for d in db.dishes.find({}, {"_id": 1})]
    return [by_hash(ids, 1), by_hash(ids, 3), by_hash(ids[::-1], 10)]


def test_new_user_invariants(client, db):
    for chosen in chosen_sets(db):
        for flt in ({}, {"veg": True}, {"meal": "sáng", "category": "đồ uống"}):
            for ra in ({}, {"region": "Nam", "age_group": "25-34"}):
                r = client.post("/api/recs/new-user", json={"food_ids": chosen, **flt, **ra})
                assert r.status_code == 200, r.text
                body = r.json()
                assert not find_key(body, "truth") and not find_key(body, "score")
                items = body["items"]
                ids = [x["food_id"] for x in items]
                assert len(items) == 10 and len(set(ids)) == 10
                assert not set(ids) & set(chosen), "mon da chon khong duoc goi y lai"
                f = DishFilter(**flt)
                assert db.dishes.count_documents({"_id": {"$in": ids}, **f.query()}) == 10
                names = {d["_id"]: d["dish_name"] for d in db.dishes.find({"_id": {"$in": chosen}}, {"dish_name": 1})}
                key = f"vùng-tuổi|{ra['region']}|{ra['age_group']}" if ra else "chung"
                pop_ids = {p["food_id"] for p in db.popular.find_one({"_id": key})["items"]}
                srcs = [x["source"] for x in items]
                # Thu tu nguon: content -> pop -> fill
                order = {"content": 0, "pop": 1, "fill": 2}
                assert [order[s] for s in srcs] == sorted(order[s] for s in srcs)
                for x in items:
                    if x["source"] == "content":
                        assert x["because"]["food_id"] in chosen
                        assert x["reason"] == f"Giống món {names[x['because']['food_id']]} bạn đã chọn"
                    elif x["source"] == "pop":
                        assert x["food_id"] in pop_ids
                s = body["summary"]
                assert s["from_recs"] + s["from_popular"] + s["from_fill"] == 10


def test_new_user_errors(client, db):
    one = db.dishes.find_one({}, {"_id": 1})["_id"]
    assert client.post("/api/recs/new-user", json={"food_ids": []}).status_code == 422
    assert client.post("/api/recs/new-user", json={"food_ids": list(range(11))}).status_code == 422
    assert client.post("/api/recs/new-user", json={"food_ids": [999999]}).status_code == 404
    assert client.post("/api/recs/new-user", json={"food_ids": [one], "region": "Tây"}).status_code == 422
    assert client.post("/api/recs/new-user", json={"food_ids": [one], "category": "không có"}).status_code == 422
