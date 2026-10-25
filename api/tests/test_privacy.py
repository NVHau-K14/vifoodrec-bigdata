"""Persona that (truth) chi duoc xuat hien o E15 va E17, kem verify_only (D14 cau 4, D15 chinh sua b).
Khong endpoint nao tra nutrition (so ngau nhien) hay score cua goi y."""
import json

from .conftest import find_key

# Chi E17 (user mau) va E15 (phan khuc) duoc co persona, kem verify_only.
# E26 tra nguyen file report (go loi, trang khong goi): report 04 va 06e co thong ke persona GOP theo cum / toan bo,
# khong co persona cua tung user -> cho phep chu "persona", nhung van cam khoa truth.
PERSONA_ALLOWED = {"/api/users/demo", "/api/segments", "/api/segments?k=3", "/api/segments?k=11",
                   "/api/reports/model_kmeans_report"}


def endpoints(db):
    uid = db.users.find_one({"group": "ấm", "history.2": {"$exists": True}}, {"_id": 1})["_id"]
    fid = db.dishes.find_one({}, {"_id": 1})["_id"]
    # Du E0-E26 (tru E20 la POST, kiem tra rieng o test_new_user_no_persona; E9, E21 khong co)
    return ["/api/health", "/api/overview", "/api/meta/filters",                                   # E0, E1, E22
            "/api/behavior/heatmap", "/api/behavior/monthly", "/api/behavior/top-dishes",            # E2, E3, E4
            "/api/behavior/lift", "/api/behavior/funnel", "/api/behavior/habits",                    # E5, E6, E7
            "/api/dishes/summary", "/api/ingredients/top", "/api/ingredients/graph",                 # E8, E10, E11
            "/api/dishes/search?q=canh", f"/api/dishes/{fid}", "/api/dishes?limit=5",                # E12, E13, E14
            "/api/segments", "/api/segments?k=3", "/api/segments?k=11", "/api/segments/8/0",         # E15, E16
            "/api/users/demo", f"/api/users/{uid}", f"/api/recs/{uid}",                              # E17, E18, E19
            "/api/eval/ranking", "/api/eval/details", "/api/trending",                               # E23, E24, E25
            "/api/reports/model_kmeans_report"]                                                      # E26


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


def test_segments_persona_marked(client):
    """E15: persona chi o truong persona_kiem_chung cua tung cum, kem verify_only."""
    for k in (3, 8, 11):
        body = client.get("/api/segments", params={"k": k}).json()
        assert body["verify_only"] is True
        for c in body["clusters"]:
            assert c["verify_only"] is True
            assert {key for key in c if "persona" in key} == {"persona_kiem_chung", "persona_share"}


def test_segment_users_no_truth(client, db):
    """E16 chi tra thong tin cong khai cua user mau, khong co persona."""
    personas = [x for x in db.users.distinct("truth.persona_main") if x]
    text = json.dumps(client.get("/api/segments/8/0").json(), ensure_ascii=False)
    assert not any(f'"{p}"' in text for p in personas)
