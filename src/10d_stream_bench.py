"""
10d_stream_bench.py - Do do tre va thong luong cua Structured Streaming (buoc 10, D18).

Do tre (moi lan chay: reset -> bat luong + replayer, hoi API E25 moi 0,5 giay):
  - su kien -> MongoDB: do tre cua su kien MOI NHAT trong batch = luc ghi MongoDB xong - emit_ts (gio that replayer
    ghi file). Can tren cho moi su kien trong batch = do tre do + 1 chu ky trigger + 1 giay (do min cua file).
  - su kien -> API: luc E25 tra ve batch moi - emit_ts moi nhat cua batch do (stream.newest_emit).
  - API -> dashboard: trang goi lai moi 5 giay (cong them toi da 5 giay, khong do o day).
Thong luong (--speed max, it file lon ghi san truoc khi bat luong, nang maxFilesPerTrigger / maxBytesPerTrigger):
  processedRowsPerSecond cua cac batch co du lieu, tong so dong / tong thoi gian, voi 2 va 4 core.
  Doi so core hay so partition thi phai reset checkpoint (moi lan chay deu reset).

Lan chay mac dinh:
  lat60    toc do 60,   trigger 5 giay, 16:00-19:00
  lat300   toc do 300,  trigger 1 giay, 16:00-21:00
  lat1200  toc do 1200, trigger 1 giay, 06:00-24:00
  thr_c2   7 ngay 21-27/09/2026 (10a --days 7), 14 file 12 gio, 2 file / trigger, 2 core
  thr_c4   nhu tren, 4 core (cum chi con luong nay chay)

Dau vao : data/stream/replay_*.jsonl.gz (10a), service api (http://api:8000)
Dau ra  : data/output/stream_report.json   khoa "bench" (giu khoa "checks" cua 10c)
Chay tren cum (tu may, xem CLAUDE.md; ~15 phut):  python src/10d_stream_bench.py [--only lat60,thr_c2]
"""
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths  # noqa: E402
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--only", default="")
ap.add_argument("--api", default=os.getenv("API_URL", "http://api:8000"))
args = ap.parse_args()

DAY = S.DEFAULT_DAY
RUNS = {
    "lat60": {"common": ["--day", DAY, "--from", "16:00", "--to", "19:00", "--speed", "60", "--late", "1"], "poll": True},
    "lat300": {"common": ["--day", DAY, "--from", "16:00", "--to", "21:00", "--speed", "300", "--late", "1"], "poll": True},
    "lat1200": {"common": ["--day", DAY, "--from", "06:00", "--to", "24:00", "--speed", "1200", "--late", "1"], "poll": True},
    "thr_c2": {"common": ["--day", "2026-09-21", "--days", "7", "--from", "00:00", "--to", "24:00", "--speed", "max",
                          "--late", "0"],
               "replay": ["--chunk-min", "720"], "stream": ["--max-files", "2", "--cores", "2"],
               "replay_first": True},
    "thr_c4": {"common": ["--day", "2026-09-21", "--days", "7", "--from", "00:00", "--to", "24:00", "--speed", "max",
                          "--late", "0"],
               "replay": ["--chunk-min", "720"], "stream": ["--max-files", "2", "--cores", "4"],
               "replay_first": True},
}
if args.only:
    RUNS = {k: v for k, v in RUNS.items() if k in args.only.split(",")}
SP, P = S.StreamPaths(), Paths()
stamp = datetime.now().strftime("%m%d_%H%M%S")


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[max(0, int(round(q * len(xs))) - 1)], 3) if xs else None


def summary(xs):
    return {"n": len(xs), "p50": pct(xs, 0.5), "p95": pct(xs, 0.95), "max": round(max(xs), 3) if xs else None,
            "mean": round(statistics.mean(xs), 3) if xs else None}


rep_file = os.path.join(P.output_local, "stream_report.json")


def save():
    """Gop ket qua vao stream_report.json (khoa bench), goi sau MOI lan chay: lan sau loi cung khong mat lan truoc."""
    report = json.load(open(rep_file, encoding="utf-8")) if os.path.exists(rep_file) else {}
    bench = report.get("bench", {})
    bench.update(out)
    bench["generated_at"] = datetime.now().isoformat(timespec="seconds")
    bench["notes"] = [
        "Độ trễ = độ trễ của sự kiện MỚI NHẤT trong batch (lúc ghi MongoDB xong − emit_ts). Sự kiện cũ nhất trong batch "
        "chờ thêm tối đa 1 chu kỳ trigger + 1 giây (độ mịn của file) → cận trên latency_bound_s.",
        "API → dashboard: trang Thời gian thực gọi lại E25 mỗi 5 giây, cộng thêm tối đa 5 giây (không đo ở đây).",
        "Thông lượng: file ghi sẵn trước khi bật luồng, 2 file / trigger; mỗi lần chạy reset checkpoint vì Spark giữ số "
        "partition của state store trong checkpoint.",
        "Dữ liệu hành vi là MÔ PHỎNG (phát lại sự kiện của bước 04).",
    ]
    report["bench"] = bench
    with open(rep_file, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    print(f"[10d] da ghi {rep_file}", flush=True)


out = {}
for name, cfg in RUNS.items():
    run_id = f"bench_{name}_{stamp}"
    print(f"[10d] {name}: {' '.join(cfg['common'])}", flush=True)
    S.reset()
    seen, api_lat = {}, []

    def poll():
        try:
            st = requests.get(f"{args.api}/api/trending", params={"limit": 1}, timeout=2).json().get("stream") or {}
        except requests.RequestException:
            return
        b, ne = st.get("data_batch_id"), st.get("newest_emit")       # batch co du lieu gan nhat
        if b is not None and ne and b not in seen:
            seen[b] = time.time()
            api_lat.append(time.time() - datetime.fromisoformat(ne).timestamp())

    times = S.run_pair(run_id, cfg["common"], stream_extra=cfg.get("stream", ()), replay_extra=cfg.get("replay", ()),
                       replay_first=cfg.get("replay_first", False), on_tick=poll if cfg.get("poll") else None)
    rd = SP.run_dir(run_id)
    batches = [json.loads(x) for x in open(os.path.join(rd, "batches.jsonl"), encoding="utf-8")]
    prog = [json.loads(x) for x in open(os.path.join(rd, "progress.jsonl"), encoding="utf-8")]
    rep = json.load(open(os.path.join(rd, "replayer.json"), encoding="utf-8"))
    data = [p for p in prog if p.get("numInputRows")]
    speed = cfg["common"][cfg["common"].index("--speed") + 1]
    trig = 5.0 if speed != "max" and float(speed) <= 60 else 1.0          # cung quy tac voi 10_stream.py
    dur = [p["durationMs"]["triggerExecution"] / 1000 for p in data]
    r = {"args": cfg["common"] + list(cfg.get("stream", ())) + list(cfg.get("replay", ())), "trigger_s": trig,
         "times_s": times, "events_replayed": rep["events"], "files": rep["files"], "rows_written": rep["rows_written"],
         "replayer_behind_max_s": rep["behind_schedule_max_s"],
         "batches_with_data": len(data), "batch_duration_s": summary(dur),
         "batches_over_trigger": sum(1 for d in dur if d > trig),
         "input_rows_per_s": summary([p["inputRowsPerSecond"] for p in data if p.get("inputRowsPerSecond")]),
         "processed_rows_per_s": summary([p["processedRowsPerSecond"] for p in data if p.get("processedRowsPerSecond")])}
    # Tach thoi gian batch: collect (Spark tinh micro-batch + gom ve driver) / ghi MongoDB (pymongo tren driver) / phan con lai
    wb = [b for b in batches if b["rows"]]
    trig_total = sum(p["durationMs"]["triggerExecution"] for p in data) / 1000
    r["sink_breakdown_s"] = {"trigger_total": round(trig_total, 1), "collect": round(sum(b["collect_ms"] for b in wb) / 1000, 1),
                             "mongo": round(sum(b["mongo_ms"] for b in wb) / 1000, 1), "cells_written": sum(b["rows"] for b in wb)}
    lat = [b["latency_s"] for b in batches if b.get("latency_s") is not None]
    if cfg.get("poll"):
        r["latency_event_to_mongo_s"] = summary(lat)
        r["latency_bound_s"] = summary([b["latency_bound_s"] for b in batches if b.get("latency_bound_s") is not None])
        r["latency_event_to_api_s"] = summary(api_lat)
        r["mongo_write_ms"] = summary([b["mongo_ms"] for b in batches if b["rows"]])
    else:
        t_first = min(datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")).timestamp() for p in data)
        t_last = max(datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")).timestamp()
                     + p["durationMs"]["triggerExecution"] / 1000 for p in data)
        rows = sum(p["numInputRows"] for p in data)
        r.update({"rows_in": rows, "data_seconds": round(t_last - t_first, 1),
                  "rows_per_s_overall": round(rows / (t_last - t_first)),
                  "durations_ms_median": {k: statistics.median(p["durationMs"].get(k, 0) for p in data)
                                          for k in ("addBatch", "getBatch", "latestOffset", "queryPlanning",
                                                    "walCommit", "commitOffsets", "triggerExecution")}})
    out[name] = r
    print(f"[10d] {name}: {json.dumps({k: v for k, v in r.items() if k != 'args'}, ensure_ascii=False)}", flush=True)
    save()

