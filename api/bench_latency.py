"""
bench_latency.py - Do do tre cac endpoint cua API (buoc 08, D15 cau 5).

Dau vao : API dang chay (mac dinh http://localhost:8000, chinh service api), MongoDB de lay tham so mau.
Dau ra  : data/output/api_report.json, khoa "latency"."<database>" (gop vao report cu, khong ghi de database khac).

Cach do:
  - moi endpoint: goi khoi dong 20 lan, roi 200 lan tuan tu qua HTTP that (httpx, giu ket noi);
  - E19 them 1 vong 10 luong song song x 100 lan (mo phong 10 nguoi xem cung luc);
  - ghi p50, p95, p99, max (ms, do o client), so request/giay, va thoi gian app / db lay tu header Server-Timing.
  - Tham so: E19, E18 xoay vong 200 user theo hash, E19 xoay 6 to hop bo loc (1 to hop chac chan phai bu mon);
    E12 xoay 50 chuoi tim lay tu ten mon that (2-3 tu dau); E13 xoay 200 mon theo hash; E20 xoay 50 bo 1-10 mon.

Chay trong container api (tu /home/jovyan/work):
  python -m api.bench_latency                                   (database cua service api, cong 8000)
  python -m api.bench_latency --base http://localhost:8001 --db vifood_local
       (truoc do chay them 1 uvicorn: MONGO_DB=vifood_local uvicorn api.main:app --port 8001)
Muc tieu: endpoint dung cache p95 < 10 ms; E12, E13, E18, E19 p95 < 50 ms; E20 p95 < 80 ms.
"""
import argparse
import hashlib
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx

from .db import get_client

REPORT = Path(__file__).resolve().parent.parent / "data" / "output" / "api_report.json"
WARMUP, N_SEQ, N_THREADS, N_PER_THREAD = 20, 200, 10, 100
FILTERS = [{}, {"veg": "true"}, {"quick": "true", "not_spicy": "true"}, {"meal": "tối"}, {"category": "canh/súp"},
           {"veg": "true", "meal": "sáng", "category": "đồ uống"}]
TARGETS = {"cache": 10, "E12": 50, "E13": 50, "E18": 50, "E19": 50, "E20": 80}


def by_hash(ids, n):
    return sorted(ids, key=lambda i: hashlib.md5(str(i).encode()).hexdigest())[:n]


def server_timing(h):
    out = {}
    for part in (h or "").split(","):
        name, _, dur = part.strip().partition(";dur=")
        if dur:
            out[name] = float(dur)
    return out


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def summarize(lat, app, db, wall):
    return {"n": len(lat), "p50_ms": round(pct(lat, 50), 2), "p95_ms": round(pct(lat, 95), 2),
            "p99_ms": round(pct(lat, 99), 2), "max_ms": round(max(lat), 2), "mean_ms": round(statistics.mean(lat), 2),
            "rps": round(len(lat) / wall, 1), "server_app_p95_ms": round(pct(app, 95), 2),
            "server_db_mean_ms": round(statistics.mean(db), 2)}


def run_seq(client, make_req, n_warm=WARMUP, n=N_SEQ):
    for i in range(n_warm):
        method, url, kw = make_req(i)
        client.request(method, url, **kw)
    lat, app, db = [], [], []
    t0 = time.perf_counter()
    for i in range(n):
        method, url, kw = make_req(i)
        t = time.perf_counter()
        r = client.request(method, url, **kw)
        lat.append((time.perf_counter() - t) * 1000)
        assert r.status_code == 200, f"{url} -> {r.status_code} {r.text[:200]}"
        st = server_timing(r.headers.get("server-timing"))
        app.append(st.get("app", 0.0))
        db.append(st.get("db", 0.0))
    return summarize(lat, app, db, time.perf_counter() - t0)


def run_parallel(base, make_req):
    def worker(w):
        out = []
        with httpx.Client(base_url=base, timeout=30) as c:
            for i in range(N_PER_THREAD):
                method, url, kw = make_req(w * N_PER_THREAD + i)
                t = time.perf_counter()
                r = c.request(method, url, **kw)
                st = server_timing(r.headers.get("server-timing"))
                out.append(((time.perf_counter() - t) * 1000, st.get("app", 0.0), st.get("db", 0.0), r.status_code))
        return out
    t0 = time.perf_counter()
    with ThreadPoolExecutor(N_THREADS) as ex:
        rows = [x for part in ex.map(worker, range(N_THREADS)) for x in part]
    wall = time.perf_counter() - t0
    assert all(r[3] == 200 for r in rows)
    return summarize([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], wall)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--db", default=None, help="database ma API do dang doc (mac dinh hoi /api/health)")
    args = ap.parse_args()

    with httpx.Client(base_url=args.base, timeout=30) as c:
        health = c.get("/api/health").json()
    dbname = args.db or health["db"]
    os.environ["MONGO_DB"] = dbname
    mdb = get_client()[dbname]
    users = by_hash([u["_id"] for u in mdb.recs.find({}, {"_id": 1})], 200)
    dishes = by_hash([d["_id"] for d in mdb.dishes.find({}, {"_id": 1})], 200)
    names = [d["dish_name"] for d in mdb.dishes.find({"_id": {"$in": by_hash(dishes, 50)}}, {"dish_name": 1})]
    queries = [" ".join(n.split()[:2 + i % 2]) for i, n in enumerate(names)]
    chosen = [dishes[i * 3:i * 3 + 1 + i % 10] for i in range(50)]
    print(f"[08] bench {args.base} database={dbname} users={len(users)} dishes={len(dishes)}", flush=True)

    G = lambda url, params=None: ("GET", url, {"params": params} if params else {})  # noqa: E731
    cases = [
        # (ma, nhom, ham tao request theo i)
        ("E1 overview", "cache", lambda i: G("/api/overview")),
        ("E2 heatmap", "cache", lambda i: G("/api/behavior/heatmap")),
        ("E3 monthly", "cache", lambda i: G("/api/behavior/monthly")),
        ("E4 top-dishes", "cache", lambda i: G("/api/behavior/top-dishes", {"slot": ["sáng", "trưa", "tối", "khuya"][i % 4]})),
        ("E5 lift", "cache", lambda i: G("/api/behavior/lift", {"group_type": ["region", "age_group", "day_type", "meal_slot"][i % 4]})),
        ("E6 funnel", "cache", lambda i: G("/api/behavior/funnel")),
        ("E7 habits", "cache", lambda i: G("/api/behavior/habits")),
        ("E8 dishes/summary", "cache", lambda i: G("/api/dishes/summary")),
        ("E15 segments", "cache", lambda i: G("/api/segments", {"k": [3, 8, 11][i % 3]})),
        ("E17 users/demo", "cache", lambda i: G("/api/users/demo")),
        ("E22 meta/filters", "cache", lambda i: G("/api/meta/filters")),
        ("E23 eval/ranking", "cache", lambda i: G("/api/eval/ranking")),
        ("E24 eval/details", "cache", lambda i: G("/api/eval/details")),
        ("E10 ingredients/top", "db", lambda i: G("/api/ingredients/top", {"seasoning": "true" if i % 2 else "false"})),
        ("E11 ingredients/graph", "db", lambda i: G("/api/ingredients/graph", {"variant": ["bỏ gia vị", "giữ gia vị"][i % 2]})),
        ("E12 dishes/search", "db", lambda i: G("/api/dishes/search", {"q": queries[i % len(queries)]})),
        ("E13 dishes/{id}", "db", lambda i: G(f"/api/dishes/{dishes[i % len(dishes)]}")),
        ("E14 dishes", "db", lambda i: G("/api/dishes", {**FILTERS[i % 6], "skip": 12 * (i % 4), "limit": 12})),
        ("E16 segments/8/{c}", "db", lambda i: G(f"/api/segments/8/{i % 8}")),
        ("E18 users/{id}", "db", lambda i: G(f"/api/users/{users[i % len(users)]}")),
        ("E19 recs/{id}", "db", lambda i: G(f"/api/recs/{users[i % len(users)]}", FILTERS[i % 6])),
        ("E20 recs/new-user", "db", lambda i: ("POST", "/api/recs/new-user", {"json": {"food_ids": chosen[i % 50]}})),
        ("E25 trending", "db", lambda i: G("/api/trending")),
    ]
    results = {}
    with httpx.Client(base_url=args.base, timeout=30) as c:
        for name, kind, mk in cases:
            r = run_seq(c, mk)
            code = name.split()[0]
            target = TARGETS.get(code, TARGETS["cache"] if kind == "cache" else None)
            r.update({"kind": kind, "target_p95_ms": target, "pass": (r["p95_ms"] < target) if target else None})
            results[name] = r
            print(f"[08] {name:24s} p50 {r['p50_ms']:7.2f}  p95 {r['p95_ms']:7.2f}  p99 {r['p99_ms']:7.2f}  "
                  f"db {r['server_db_mean_ms']:6.2f}  {r['rps']:7.1f} req/s", flush=True)
    par = run_parallel(args.base, lambda i: G(f"/api/recs/{users[i % len(users)]}", FILTERS[i % 6]))
    par.update({"threads": N_THREADS, "per_thread": N_PER_THREAD})
    print(f"[08] E19 song song {N_THREADS}x{N_PER_THREAD}: p50 {par['p50_ms']} p95 {par['p95_ms']} {par['rps']} req/s", flush=True)

    rep = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    lat = rep.setdefault("latency", {})
    lat[dbname] = {"measured_at": datetime.now().isoformat(timespec="seconds"), "base": args.base,
                   "counts": health["counts"], "warmup": WARMUP, "sequential_n": N_SEQ,
                   "endpoints": results, "e19_parallel": par,
                   "all_targets_met": all(v["pass"] for v in results.values() if v["pass"] is not None)}
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[08] ghi {REPORT} (latency.{dbname})", flush=True)


if __name__ == "__main__":
    main()
