"""Doi chieu endpoint dot 2 voi MongoDB (E4, E5, E7, E8, E10, E11, E15, E16, E25). Bat bien, dung voi ca 2 database."""
import pytest

from api.labels import FEATURES

SLOTS = ["sáng", "trưa", "tối", "khuya"]
GROUP_TYPES = ["region", "age_group", "day_type", "meal_slot"]
ATTRS = ["dish_category", "main_protein", "main_method", "dish_type_fixed", "is_quick", "is_spicy"]


@pytest.mark.parametrize("slot", SLOTS)
def test_top_dishes_by_slot(client, db, slot):
    for by, key in (("cooks", "cooks"), ("lift", "lift")):
        items = client.get("/api/behavior/top-dishes", params={"slot": slot, "by": by}).json()["items"]
        assert 1 <= len(items) <= 10
        assert [x["rank"] for x in items] == sorted(x["rank"] for x in items)
        vals = [x[key] for x in items]
        assert vals == sorted(vals, reverse=True), f"{slot}/{by} khong giam dan"
        ids = [x["food_id"] for x in items]
        assert db.dishes.count_documents({"_id": {"$in": ids}}) == len(ids)
    assert client.get("/api/behavior/top-dishes", params={"limit": 11}).status_code == 422


@pytest.mark.parametrize("group_type", GROUP_TYPES)
def test_lift_cells(client, group_type):
    for attr in ATTRS:
        r = client.get("/api/behavior/lift", params={"group_type": group_type, "attribute": attr}).json()
        assert r["groups"] and r["values"]
        for g in r["groups"]:
            cells = [c for c in r["cells"] if c["group_value"] == g]
            # Ty trong trong mot nhom cong lai ~ 100% (lam tron 2 chu so moi o)
            assert abs(sum(c["share_pct"] for c in cells) - 100) < 0.6, (group_type, attr, g)
            for c in cells:
                if c["cooks"] < r["min_cooks"]:
                    assert c["lift"] is None
                else:
                    assert c["lift"] == pytest.approx(c["share_pct"] / c["overall_pct"], rel=0.05, abs=0.02)
        overall = [v["overall_pct"] for v in r["values"]]
        assert overall == sorted(overall, reverse=True)


def test_habits(client):
    h = client.get("/api/behavior/habits").json()
    for slot in {r["meal_slot"] for r in h["session_size"]}:
        assert abs(sum(r["share_pct"] for r in h["session_size"] if r["meal_slot"] == slot) - 100) < 0.2
    assert abs(sum(r["share_pct"] for r in h["rating_dist"]) - 100) < 0.2
    assert h["repeat_by_category"][0]["dish_category"] == "Tất cả"


def test_habits_match_reports(client, full_db):
    """So voi overview va analysis_report: chi dung voi vifood (o vifood_local, reports la file cua cum)."""
    h = client.get("/api/behavior/habits").json()
    ov = client.get("/api/overview").json()
    assert sum(r["count"] for r in h["rating_dist"]) == ov["events_by_type"]["rate"]
    funnel_users = client.get("/api/behavior/funnel").json()["users"]["users"]
    assert sum(r["users"] for r in h["user_activity"]) == funnel_users
    km = client.get("/api/reports/model_kmeans_report").json()
    assert client.get("/api/segments").json()["n_users"] == km["users"]


def test_dishes_summary(client, db):
    s = client.get("/api/dishes/summary").json()
    k = s["kpi"]
    n = db.dishes.count_documents({})
    assert k["n_dishes"] == n
    assert k["veg_pct"] == round(100 * db.dishes.count_documents({"is_vegetarian": True}) / n, 2)
    assert k["quick_pct"] == round(100 * db.dishes.count_documents({"is_quick": True}) / n, 2)
    assert sum(r["n_dishes"] for r in s["by_type"]) == n
    for attr, rows in s["catalog_vs_cooked"].items():
        assert abs(sum(r["catalog_pct"] for r in rows) - 100) < 0.6, attr
        assert abs(sum(r["cook_pct"] for r in rows) - 100) < 0.6, attr
    curve = [r["cooks_cum_pct"] for r in s["long_tail"]["curve"]]
    assert curve == sorted(curve) and curve[-1] == pytest.approx(100, abs=0.1)


def test_ingredients(client):
    no_s = client.get("/api/ingredients/top", params={"limit": 50}).json()
    assert len(no_s) == 50 and not any(r["is_seasoning"] for r in no_s)
    assert [r["rank"] for r in no_s] == list(range(1, 51))
    assert [r["cooks"] for r in no_s] == sorted((r["cooks"] for r in no_s), reverse=True)
    with_s = client.get("/api/ingredients/top", params={"limit": 50, "seasoning": True}).json()
    assert any(r["is_seasoning"] for r in with_s)
    for variant in ("bỏ gia vị", "giữ gia vị"):
        g = client.get("/api/ingredients/graph", params={"variant": variant, "limit": 150}).json()
        lifts = [e["lift"] for e in g["edges"]]
        assert lifts == sorted(lifts, reverse=True)
        assert sum(n["degree"] for n in g["nodes"]) == 2 * len(g["edges"])
        assert {n["name"] for n in g["nodes"]} == {e[k] for e in g["edges"] for k in ("src", "dst")}


@pytest.mark.parametrize("k", [3, 8, 11])
def test_segments(client, db, k):
    s = client.get("/api/segments", params={"k": k}).json()
    assert s["verify_only"] is True and s["k"] == k
    assert len(s["clusters"]) == k == db.clusters.count_documents({"k": k})
    assert sum(c["n_users"] for c in s["clusters"]) == s["n_users"]
    for f in FEATURES:
        # z giua cac cum: trung binh 0
        assert abs(sum(c["z"][f] for c in s["clusters"]) / k) < 1e-2, f
    # Moi cum 1 cau de xuat dac trung nhat; khong cum nao lap cau cua cum khac (D16)
    strategies = [c["strategy"][0] for c in s["clusters"]]
    assert len(set(strategies)) == len(strategies), strategies
    for c in s["clusters"]:
        assert c["label"] and len(c["strategy"]) == 1 and len(c["top_features"]) == 3
        assert c["verify_only"] is True and c["persona_kiem_chung"]
    assert client.get("/api/segments", params={"k": 5}).status_code == 422


def test_segment_users(client, db):
    for c in range(8):
        r = client.get(f"/api/segments/8/{c}", params={"sample": 5}).json()
        n = db.users.count_documents({"cluster_k8": c})
        assert r["n_users"] == n
        for key in ("by_region", "by_age", "by_group"):
            assert sum(x["n_users"] for x in r[key]) == n
        ids = [u["user_id"] for u in r["sample_users"]]
        assert ids == sorted(ids) and len(ids) == 5
        assert db.users.count_documents({"_id": {"$in": ids}, "cluster_k8": c}) == len(ids)
    assert client.get("/api/segments/8/99").status_code == 404
    # cung so voi cum k = 8 cua E15
    seg = client.get("/api/segments", params={"k": 8}).json()
    assert {c["cluster"]: c["n_users"] for c in seg["clusters"]} == {
        c: db.users.count_documents({"cluster_k8": c}) for c in range(8)}


def test_trending(client, db):
    r = client.get("/api/trending").json()
    if db.trending.estimated_document_count() == 0:
        assert r == {"status": "chưa chạy", "updated_at": None, "windows": []}
    else:
        assert r["status"] == "đang chạy" and r["windows"]


def test_food_ids_exist(client, db):
    """food_id trong E4, E13 (tuong tu, an kem), E19 deu co trong dishes."""
    ids = set()
    for slot in SLOTS:
        ids |= {x["food_id"] for x in client.get("/api/behavior/top-dishes", params={"slot": slot}).json()["items"]}
    fid = db.dishes.find_one({"companions.0": {"$exists": True}}, {"_id": 1})["_id"]
    d = client.get(f"/api/dishes/{fid}").json()
    ids |= {x["food_id"] for x in d["similar"] + d["companions"]}
    uid = db.recs.find_one({}, {"_id": 1})["_id"]
    ids |= {x["food_id"] for x in client.get(f"/api/recs/{uid}").json()["items"]}
    assert db.dishes.count_documents({"_id": {"$in": list(ids)}}) == len(ids)
