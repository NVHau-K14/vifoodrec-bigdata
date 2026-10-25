"""Persona that (truth) chi duoc xuat hien o E15 va E17, kem verify_only (D14 cau 4, D15 chinh sua b).
Khong endpoint nao tra nutrition (so ngau nhien) hay score cua goi y."""
import json

from .conftest import find_key

# E15 (phan khuc) se them o dot 2
PERSONA_ALLOWED = {"/api/users/demo"}


def endpoints(db):
    uid = db.users.find_one({"group": "ấm", "history.2": {"$exists": True}}, {"_id": 1})["_id"]
    fid = db.dishes.find_one({}, {"_id": 1})["_id"]
    return ["/api/health", "/api/overview", "/api/meta/filters", "/api/behavior/heatmap", "/api/behavior/monthly",
            "/api/behavior/funnel", "/api/dishes?limit=5", "/api/dishes/search?q=canh", f"/api/dishes/{fid}",
            "/api/users/demo", f"/api/users/{uid}", f"/api/recs/{uid}", "/api/eval/ranking", "/api/eval/details"]


def test_no_truth_outside_allowed(client, db):
    for path in endpoints(db):
        r = client.get(path)
        assert r.status_code == 200, path
        body = r.json()
        assert not find_key(body, "truth"), path
        assert not find_key(body, "nutrition"), path
        if path not in PERSONA_ALLOWED:
            assert not find_key(body, "persona", substring=True), path


def test_persona_values_not_leaked(client, db):
    """Gia tri persona (vd "bận rộn") khong duoc nam trong ho so hay goi y cua user."""
    personas = [x for x in db.users.distinct("truth.persona_main") if x]
    uid = db.users.find_one({"group": "ấm", "history.2": {"$exists": True}}, {"_id": 1})["_id"]
    for path in (f"/api/users/{uid}", f"/api/recs/{uid}"):
        text = json.dumps(client.get(path).json(), ensure_ascii=False)
        assert not any(f'"{p}"' in text for p in personas), path


def test_new_user_no_persona(client, db):
    fid = db.dishes.find_one({}, {"_id": 1})["_id"]
    body = client.post("/api/recs/new-user", json={"food_ids": [fid]}).json()
    assert not find_key(body, "persona", substring=True)


def test_demo_users_persona_marked(client, db):
    body = client.get("/api/users/demo").json()
    assert body["verify_only"] is True
    personas = [x for x in db.users.distinct("truth.persona_main") if x]
    assert sorted(p["persona"] for p in body["by_persona"]) == sorted(personas)
    for p in body["by_persona"]:
        assert p["verify_only"] is True and len(p["users"]) == 2
        for u in p["users"]:
            assert db.users.find_one({"_id": u["user_id"]})["truth"]["persona_main"] == p["persona"]
    for g, us in body["by_group"].items():
        assert len(us) == 3 and all(u["group"] == g for u in us)
