"""E1, E2, E3, E6, E14, E23, E24: so tren API khop voi MongoDB (khong chep cung)."""


def test_overview_and_pipeline(client, db):
    ov = client.get("/api/overview").json()
    doc = db.overview.find_one({"_id": "overview"})
    assert ov["n_events"] == doc["n_events"] and ov["n_dishes"] == doc["n_dishes"]
    assert ov["hdfs_total"]["bytes"] == sum(v["bytes"] for v in doc["hdfs"].values())
    steps = {s["step"]: s["status"] for s in ov["pipeline"]}
    assert steps["07"] == "Xong" and steps["08"] == "Đang làm"


def test_heatmap_168_cells(client):
    cells = client.get("/api/behavior/heatmap").json()["cells"]
    assert len(cells) == 168 and len({(c["dow_idx"], c["hour"]) for c in cells}) == 168


def test_monthly_total_equals_overview(client, db, full_db):
    m = client.get("/api/behavior/monthly").json()
    ev = db.overview.find_one({"_id": "overview"})["events_by_type"]
    assert sum(x["cooks"] for x in m["months"]) == ev["cook"]
    assert sum(x["views"] for x in m["months"]) == ev["view"]
    assert [x["split"] for x in m["months"]][-2:] == ["val", "test"]
    assert m["tet_month"] == max(m["months"], key=lambda x: x["tet_share_pct"] or 0)["month"]


def test_funnel(client):
    f = client.get("/api/behavior/funnel").json()
    assert f["pairs"]["view"] >= f["pairs"]["cook"] >= f["pairs"]["rate"]
    assert len(f["by_category"]) >= 10


def test_top_dishes_sorted(client):
    items = client.get("/api/dishes", params={"limit": 5}).json()["items"]
    assert [x["cook_rank"] for x in items] == sorted(x["cook_rank"] for x in items)


def test_eval_matches_models_metrics(client, db, full_db):
    r = client.get("/api/eval/ranking").json()
    hy = next(x for x in r["rows"] if x["model"] == "hybrid")["metrics"]["ndcg@10"]
    mm = db.reports.find_one({"_id": "models_metrics"})["content"]["ranking"]
    ref = next(x for x in mm if x["view"] == "test" and x["model"] == "hybrid" and x["variant"] == "chính"
               and x["group"] == "tất cả")["ndcg@10"]
    assert hy == ref
    assert r["ci95"] and all(c["ci95"][0] <= c["hieu"] <= c["ci95"][1] for c in r["ci95"])
    d = client.get("/api/eval/details").json()
    assert len(d["rmse"]["rows"]) == 3 and d["als_grid"] and d["lsh"] and d["timings"]


def test_perf_matches_collection(client, db):
    """E24.perf (D17): so tren API khop collection perf; speedup = T(1 worker) / T(2 worker); buoc 09 'Xong'."""
    p = client.get("/api/eval/details").json()["perf"]
    steps = {s["step"]: s["status"] for s in client.get("/api/overview").json()["pipeline"]}
    if not db.perf.find_one({"_id": "summary"}):
        assert p == {"available": False} and steps["09"] == "Chưa"
        return
    assert p["available"] and steps["09"] == "Xong"
    assert len(p["rows"]) == db.perf.count_documents({"kind": "job"})
    for r in p["rows"]:
        if r["median_s"] is not None:
            assert r["min_s"] <= r["median_s"] <= r["max_s"] and len(r["runs_s"]) == r["n_ok"]
    assert p["speedup"]
    for s in p["speedup"]:
        t1 = db.perf.find_one({"_id": f"{s['job']}|{s['level']}|w1"})["median_s"]
        t2 = db.perf.find_one({"_id": f"{s['job']}|{s['level']}|w2"})["median_s"]
        assert s["t_1w_s"] == t1 and s["t_2w_s"] == t2 and abs(s["speedup"] - t1 / t2) < 0.006
    # speedup theo muc: chuoi lay tu chain_totals, job lay tu rows; du 3 muc cho chuoi va 04, 05, 06b
    chain = {(c["level"], c["workers"]): c["total_s"] for c in p["chain_totals"] if c["complete"]}
    med = {(r["level"], r["workers"], r["job"]): r["median_s"] for r in p["rows"]}
    bs = p["speedup_by_scale"]
    assert {(b["key"], b["level"]) for b in bs} == {(k, lv) for k in ("chain", "04", "05", "06b")
                                                     for lv in ("s010", "s050", "s100")}
    for b in bs:
        t1, t2 = ((chain[(b["level"], w)] if b["key"] == "chain" else med[(b["level"], w, b["key"])]) for w in (1, 2))
        assert b["t_1w_s"] == t1 and b["t_2w_s"] == t2 and abs(b["speedup"] - t1 / t2) < 0.006
