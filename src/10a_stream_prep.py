"""
10a_stream_prep.py - Chuan bi doan phat lai cho Structured Streaming (buoc 10, D18).

Lay su kien MO PHONG cua mot (hoac vai) ngay tu bang events (buoc 04), gan event_id theo thu tu thoi gian,
ghi file JSON Lines nen de replayer (10b) phat lai, va tinh DAP AN bang Spark batch: so dem theo
cua so 60 phut truot 15 phut x vung x mon, cung dinh nghia voi luong (stream_common.aggregate).
Dap an chi tinh su kien co ts trong [--from, --to) (replayer chi phat khoang nay).

Dau vao : HDFS /data/events/events, /data/events/users
Dau ra  : data/stream/replay_<ngay>[_<n>d].jsonl.gz      su kien sap theo ts (replayer doc)
          HDFS /data/stream/replay/<ngay>[_<n>d]          ban Parquet (10c doc de tinh lai dap an)
          HDFS /data/stream/truth/<ngay>_<HHMM>-<HHMM>    dap an (chi khi --days 1)
          data/output/stream_prep_report.json             {doan: so su kien theo loai / gio, dap an, cua so dong nhat}

Chay tren cum (tu may, xem CLAUDE.md):
  python src/10a_stream_prep.py                          # CN 27/09/2026, dap an 06:00-24:00
  python src/10a_stream_prep.py --days 7 --day 2026-09-21   # 7 ngay lien (do thong luong, khong tinh dap an)
Chay thu local:  python src/10a_stream_prep.py --local
"""
import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timedelta

from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, Timer, get_spark  # noqa: E402
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--day", default=S.DEFAULT_DAY)
ap.add_argument("--days", type=int, default=1)
ap.add_argument("--from", dest="t_from", default="06:00", help="dap an chi tinh ts >= gio nay")
ap.add_argument("--to", dest="t_to", default="24:00")
ap.add_argument("--local", action="store_true")
args = ap.parse_args()

spark = get_spark("10a_stream_prep", local=args.local)
P, SP, T = Paths(args.local), S.StreamPaths(args.local), Timer("10")
d0 = datetime.fromisoformat(args.day)
d1 = d0 + timedelta(days=args.days)
tag = f"{args.day}{'' if args.days == 1 else f'_{args.days}d'}"
months = sorted({(d0 + timedelta(days=i)).strftime("%Y-%m") for i in range(args.days)})

T.mark("read_events")
events = (spark.read.parquet(f"{P.events}/events")
          .where(F.col("month").isin(months))
          .where((F.col("ts") >= F.lit(d0.strftime("%Y-%m-%d 00:00:00")).cast("timestamp"))
                 & (F.col("ts") < F.lit(d1.strftime("%Y-%m-%d 00:00:00")).cast("timestamp")))
          .drop("month"))
# event_id theo thu tu thoi gian (tat dinh: hoa thi theo phien, user, mon, loai)
order = Window.orderBy("ts", "session_id", "user_id", "food_id", "event_type")
events = events.withColumn("event_id", F.row_number().over(order).cast("long")).cache()
n = events.count()
print(f"[10] {n:,} su kien tu {args.day} ({args.days} ngay)", flush=True)

T.mark("write_replay")
events.write.mode("overwrite").parquet(SP.uri(f"{SP.replay}/{tag}"))
os.makedirs(SP.work, exist_ok=True)
rows = (events.select("event_id", "user_id", "food_id", "event_type",
                      F.date_format("ts", "yyyy-MM-dd'T'HH:mm:ss.SSSXXX").alias("ts"),
                      "meal_slot", "session_id", "rating")
              .orderBy("ts", "event_id").toLocalIterator())
with gzip.open(SP.replay_file(args.day, args.days), "wt", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r.asDict(), ensure_ascii=False) + "\n")
print(f"[10] da ghi {SP.replay_file(args.day, args.days)} ({os.path.getsize(SP.replay_file(args.day, args.days)) / 2**20:.1f} MB)",
      flush=True)

T.mark("stats")
by_type = {r["event_type"]: r["count"] for r in events.groupBy("event_type").count().collect()}
by_hour = {f"{r['day']} {r['hour']:02d}": {"events": r["events"], "cooks": r["cooks"]}
           for r in events.groupBy(F.date_format("ts", "yyyy-MM-dd").alias("day"), F.hour("ts").alias("hour"))
                          .agg(F.count("*").alias("events"), F.sum((F.col("event_type") == "cook").cast("int")).alias("cooks"))
                          .orderBy("day", "hour").collect()}
report = {"day": args.day, "days": args.days, "events": n, "events_by_type": by_type, "by_hour": by_hour,
          "replay_file": os.path.relpath(SP.replay_file(args.day, args.days), S.PROJECT_DIR).replace("\\", "/"),
          "replay_file_mb": round(os.path.getsize(SP.replay_file(args.day, args.days)) / 2**20, 2),
          "hdfs_replay": f"{SP.replay}/{tag}"}

if args.days == 1:
    T.mark("truth")
    lo, hi = S.sim_bounds(args.day, args.t_from, args.t_to)
    users = spark.read.parquet(f"{P.events}/users")
    sel = events.where((F.col("ts") >= F.lit(lo.isoformat()).cast("timestamp"))
                       & (F.col("ts") < F.lit(hi.isoformat()).cast("timestamp")))
    truth = S.aggregate(sel.where(F.col("event_type").isin(S.TYPES))
                           .join(users.select("user_id", "region"), "user_id")
                           .withColumn("emit_ts", F.lit(None).cast("timestamp")))
    tpath = f"{SP.truth}/{args.day}_{args.t_from.replace(':', '')}-{args.t_to.replace(':', '')}"
    truth.write.mode("overwrite").parquet(SP.uri(tpath))
    cells = [r.asDict() for r in spark.read.parquet(SP.uri(tpath)).collect()]
    by_ws = {}
    for c in cells:
        by_ws.setdefault(c["ws"], []).append(c)
    docs = {ws: S.window_docs(ws, cs, by_ws.get(ws - S.WINDOW_MIN * 60, [])) for ws, cs in by_ws.items()}
    peak_ws = max(docs, key=lambda ws: docs[ws]["all"]["total_cooks"])
    peak = docs[peak_ws]["all"]
    report["expected"] = {   # dap an batch (khong lien quan users_truth)
        "from": args.t_from, "to": args.t_to, "hdfs": tpath, "cells": len(cells), "windows": len(docs),
        "events_in_range": sel.count(),
        "events_counted": sel.where(F.col("event_type").isin(S.TYPES)).count(),
        "peak_window": {"window_start": S.iso(peak["window_start"]), "meal_slot": peak["meal_slot"],
                        "total_cooks": peak["total_cooks"], "total_views": peak["total_views"],
                        "n_dishes": peak["n_dishes"], "top5": peak["items"][:5]},
        "cooks_per_window": {S.doc_id(ws, "all"): docs[ws]["all"]["total_cooks"] for ws in sorted(docs)},
    }
    print(f"[10] dap an {tpath}: {len(cells):,} o, {len(docs)} cua so; cua so dong nhat {S.doc_id(peak_ws, 'all')} "
          f"{peak['total_cooks']} luot nau", flush=True)

T.mark()
report["timings_s"], report["total_seconds"] = T.parts, T.total()
# 1 file cho moi doan phat lai (khoa = <ngay>[_<n>d]), chay doan khac khong ghi de
rep_file = os.path.join(P.output_local, "stream_prep_report.json")
allrep = json.load(open(rep_file, encoding="utf-8")) if os.path.exists(rep_file) else {}
allrep[tag] = report
with open(rep_file, "w", encoding="utf-8") as fh:
    json.dump(allrep, fh, ensure_ascii=False, indent=2)
print(f"[10] xong sau {report['total_seconds']}s", flush=True)
spark.stop()
