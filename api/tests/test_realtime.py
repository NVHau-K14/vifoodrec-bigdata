"""E25 (Structured Streaming, D18): dang tra ve khi trong / co du lieu, khop collection trending."""
from datetime import datetime, timezone

SCOPES = ["all", "Bắc", "Trung", "Nam"]


def test_trending_empty_or_consistent(client, db):
    r = client.get("/api/trending").json()
    assert r["scopes"] == SCOPES and r["scope"] == "all"
    if not db.trending.estimated_document_count() and not db.stream_status.find_one({"_id": "current"}):
        assert r["status"] == "chưa chạy" and r["current"] is None and r["series"]["windows"] == []
        return
    assert r["status"] in ("đang chạy", "đã dừng")
    st = db.stream_status.find_one({"_id": "current"})
    cur = r["current"]
    assert cur is not None
    # "1 gio qua" = cua so gan nhat da ket thuc theo gio mo phong
    assert cur["window_end"] <= r["stream"]["sim_now"]
    assert all(w["window_end"] > r["stream"]["sim_now"] for w in r["in_progress"])
    # khop collection: doc cua cua so hien tai (pymongo tra datetime UTC khong mui gio)
    we = datetime.fromisoformat(cur["window_end"]).astimezone(timezone.utc).replace(tzinfo=None)
    doc = db.trending.find_one({"scope": "all", "window_end": we})
    assert doc and doc["total_cooks"] == cur["total_cooks"]
    # items giam dan theo cooks, hang 1..n, delta = cooks - prev_cooks
    items = cur["items"]
    assert [i["rank"] for i in items] == list(range(1, len(items) + 1))
    assert all(a["cooks"] >= b["cooks"] for a, b in zip(items, items[1:]))
    assert all(i["delta"] == i["cooks"] - i["prev_cooks"] for i in items)
    assert all(x["delta"] > 0 for x in cur["rising"])
    # chot: window_end <= watermark
    if st.get("watermark"):
        assert cur["final"] == (cur["window_end"] <= r["stream"]["watermark"])


def test_trending_regions_sum_to_all(client, db):
    """Tong luot nau 3 vung = toan quoc o moi cua so (series cua E25 va trong collection)."""
    r = client.get("/api/trending", params={"windows": 48}).json()
    if not r["series"]["windows"]:
        return
    for i in range(len(r["series"]["windows"])):
        regs = [r["series"][s][i] for s in SCOPES[1:]]
        if None not in regs and r["series"]["all"][i] is not None:
            assert sum(regs) == r["series"]["all"][i]
    tot = {}
    for d in db.trending.find({}, {"window_start": 1, "scope": 1, "total_cooks": 1}):
        tot.setdefault(d["window_start"], {})[d["scope"]] = d["total_cooks"]
    for ws, t in tot.items():
        if len(t) == 4:
            assert t["all"] == t["Bắc"] + t["Trung"] + t["Nam"], ws


def test_trending_scope_filter(client, db):
    if not db.trending.estimated_document_count():
        return
    for s in SCOPES[1:]:
        r = client.get("/api/trending", params={"scope": s, "limit": 5}).json()
        assert r["scope"] == s
        if r["current"]:
            assert len(r["current"]["items"]) <= 5
