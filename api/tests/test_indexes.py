"""Cac truy van chinh cua API dung index (khong COLLSCAN); truy van bu mon khong sap xep trong bo nho."""
from pymongo import ASCENDING

from api.dishes_common import CARD_PROJ


def stages(plan):
    out = []
    stack = [plan]
    while stack:
        p = stack.pop()
        out.append(p.get("stage", ""))
        if p.get("inputStage"):
            stack.append(p["inputStage"])
        stack.extend(p.get("inputStages", []))
    return out


def winning(cursor):
    return stages(cursor.explain()["queryPlanner"]["winningPlan"])


def test_queries_use_indexes(db):
    uid = db.recs.find_one({}, {"_id": 1})["_id"]
    ids = [x["food_id"] for x in db.recs.find_one({"_id": uid})["items"]]
    persona = db.users.find_one({"truth.persona_main": {"$ne": None}})["truth"]["persona_main"]
    plans = {
        "recs theo user": winning(db.recs.find({"_id": uid})),
        "loc 50 mon goi y": winning(db.dishes.find({"_id": {"$in": ids}, "is_vegetarian": True}, CARD_PROJ)),
        "bu mon": winning(db.dishes.find({"is_vegetarian": True, "meal_types": "sáng", "_id": {"$nin": ids}}, CARD_PROJ)
                          .sort("stats.cook_rank", ASCENDING).limit(10)),
        "tim mon": winning(db.dishes.find({"name_search": {"$regex": "dau hu"}}, CARD_PROJ)
                           .sort("stats.cook_rank", ASCENDING).limit(20)),
        "user mau theo persona": winning(db.users.find({"truth.persona_main": persona, "group": "ấm"}).sort("_id", 1).limit(2)),
        "user theo id": winning(db.users.find({"_id": uid}, {"truth": 0})),
    }
    for name, st in plans.items():
        assert "COLLSCAN" not in st, f"{name}: {st}"
        assert any(s in ("IXSCAN", "IDHACK", "EXPRESS_IXSCAN", "EXPRESS_IDHACK") for s in st), f"{name}: {st}"
    assert "SORT" not in plans["bu mon"], plans["bu mon"]
