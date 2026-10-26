"""
10_stream.py - Spark Structured Streaming: mon thinh hanh theo cua so thoi gian (buoc 10, D18).

Doc file JSON Lines do replayer (10b) dua vao HDFS /data/stream/incoming, tinh so luot nau / xem / luu
theo cua so 60 phut truot 15 phut x vung x mon (thoi gian su kien, watermark 10 phut), roi ghi MongoDB:

  readStream.json (schema co dinh, maxFilesPerTrigger, cleanSource=archive)
   -> withWatermark("ts", 10 phut) -> dropDuplicatesWithinWatermark(event_id) -> loc cook/view/favorite
   -> join broadcast(users) lay vung -> groupBy(window 60/15, vung, mon) -> outputMode update
   -> foreachBatch: trending_cells (so dem tuyet doi, upsert theo _id -> idempotent)
                    trending (top 20 + "tang nhanh" cho toan quoc va 3 vung, moi cua so bi cham)
                    stream_status (heartbeat, do tre, watermark, so dong bi bo)

Idempotent: o luu so dem TUYET DOI cua trang thai, ghi lai cung batch cho cung gia tri. last_batch_id luu kem
query.id: chay lai tu checkpoint thi bo qua batch da ghi; query moi (sau reset) thi khong bo qua.
Doi --cores / --partitions / dinh nghia cua so ma checkpoint con thi dung lai (phai reset), vi Spark giu
cau hinh trong checkpoint.

Dau vao : HDFS /data/stream/incoming/*.jsonl, /data/events/users
Dau ra  : MongoDB trending, trending_cells, stream_status; checkpoint HDFS /data/stream/checkpoint
          data/stream/runs/<run_id>/{batches,progress}.jsonl   tung batch: do tre, so dong; tien do cua Spark

Chay (thuong do scripts/10_stream.sh, 10c hoac 10d goi; Spark UI cua luong o http://localhost:4041):
  python src/10_stream.py --run-id demo --speed 60 --trigger 5
  python src/10_stream.py --run-id t1 --exit-when-done        # dung khi replayer xong va moi cua so da chot
"""
import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

from pymongo import ReplaceOne, UpdateOne
from pyspark.sql.streaming import StreamingQueryListener

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, get_spark  # noqa: E402
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--run-id", required=True)
ap.add_argument("--day", default=S.DEFAULT_DAY, help="ngay phat lai (hien thi tren dashboard, tinh moc ket thuc)")
ap.add_argument("--days", type=int, default=1)
ap.add_argument("--from", dest="t_from", default="06:00")
ap.add_argument("--to", dest="t_to", default="24:00")
ap.add_argument("--speed", default="60")
ap.add_argument("--late", type=int, default=1)
ap.add_argument("--trigger", type=float, default=None, help="giay; mac dinh 5 o speed <= 60, 1 o speed cao hon")
ap.add_argument("--max-files", type=int, default=10, help="maxFilesPerTrigger")
ap.add_argument("--max-bytes", default=None, help="maxBytesPerTrigger (so byte; thay cho --max-files)")
ap.add_argument("--cores", type=int, default=2, help="spark.cores.max")
ap.add_argument("--partitions", type=int, default=4, help="spark.sql.shuffle.partitions (state store)")
ap.add_argument("--filter-before-dedup", action="store_true", help="loc truoc khu trung: tick khong day duoc watermark (D18, chi de thu)")
ap.add_argument("--exit-when-done", action="store_true", help="dung khi replayer xong va watermark qua moi cua so")
ap.add_argument("--local", action="store_true")
args = ap.parse_args()
if args.trigger is None:
    args.trigger = 5.0 if args.speed != "max" and float(args.speed) <= 60 else 1.0

SP, P, fs = S.StreamPaths(args.local), Paths(args.local), S.FS(args.local)
run_dir = SP.run_dir(args.run_id)
db = S.mongo_db(args.local)
_, hi = S.sim_bounds(args.day, args.t_from, args.t_to)
hi += timedelta(days=args.days - 1)

# Cau hinh nam trong checkpoint: doi thi phai reset (Spark giu so partition cua state store tu lan dau)
CONF = {"cores": args.cores, "partitions": args.partitions, "window": S.WINDOW, "slide": S.SLIDE,
        "watermark": S.WATERMARK, "filter_before_dedup": args.filter_before_dedup}
if fs.exists(SP.checkpoint) and fs.exists(SP.checkpoint_conf):
    old = json.loads(fs.read(SP.checkpoint_conf))
    if old != CONF:
        sys.exit(f"[10] checkpoint dang dung cau hinh {old}, khac {CONF}. Chay 'scripts/10_stream.sh reset' truoc.")

spark = get_spark(f"10_stream|{args.run_id}", local=args.local, conf={
    "spark.cores.max": str(args.cores), "spark.executor.memory": "1g", "spark.driver.memory": "1g",
    "spark.sql.shuffle.partitions": str(args.partitions), "spark.ui.port": "4041",
    "spark.sql.streaming.metricsEnabled": "true"})
users = spark.read.parquet(f"{P.events}/users").select("user_id", "region").cache()
users.count()

reader = (spark.readStream.schema(S.EVENT_SCHEMA)
          .option("cleanSource", "archive").option("sourceArchiveDir", SP.uri(SP.archive)))
# Spark khong cho dat dong thoi maxFilesPerTrigger va maxBytesPerTrigger (so byte nguyen)
if args.max_bytes:
    reader = reader.option("maxBytesPerTrigger", int(args.max_bytes))
else:
    reader = reader.option("maxFilesPerTrigger", args.max_files)
events = reader.json(SP.uri(SP.incoming))
cells = S.stream_query(events, users, filter_before_dedup=args.filter_before_dedup)

# ---------------------------------------------------------------------------
# Trang thai chung giua foreachBatch va listener (cung tien trinh driver)
# ---------------------------------------------------------------------------
state = {"latencies": [], "n_batches": 0, "dropped": {}, "query_id": None}
status_base = {"run_id": args.run_id, "replay": {"day": args.day, "from": args.t_from, "to": args.t_to,
                                                  "days": args.days, "speed": args.speed, "late": args.late},
               "trigger_s": args.trigger, "conf": CONF}
batches_log = open(os.path.join(run_dir, "batches.jsonl"), "a", encoding="utf-8")
progress_log = open(os.path.join(run_dir, "progress.jsonl"), "a", encoding="utf-8")


def set_status(**kw):
    db.stream_status.update_one({"_id": "current"}, {"$set": {**kw, "updated_at": datetime.now(timezone.utc)}},
                                upsert=True)


def sink(df, batch_id):
    """foreachBatch: df = cac o vua doi, so dem tuyet doi."""
    t_start = time.time()
    st = db.stream_status.find_one({"_id": "current"}, {"query_id": 1, "last_batch_id": 1}) or {}
    if st.get("query_id") == state["query_id"] and st.get("last_batch_id") is not None and batch_id <= st["last_batch_id"]:
        print(f"[10] bo qua batch {batch_id} (da ghi, query {state['query_id']})", flush=True)
        return
    rows = [r.asDict() for r in df.collect()]
    t_collect = time.time()
    if rows:
        db.trending_cells.bulk_write([
            UpdateOne({"_id": S.cell_id(r["ws"], r["region"], r["food_id"])},
                      {"$set": {"ws": r["ws"], "region": r["region"], "food_id": r["food_id"],
                                **{k: r[k] for k in S.CELL_COUNTS}, "last_emit_ms": r["last_emit_ms"]}},
                      upsert=True) for r in rows], ordered=False)
        touched = sorted({r["ws"] for r in rows})
        need = sorted(set(touched) | {ws - S.WINDOW_MIN * 60 for ws in touched})
        by_ws = {}
        for c in db.trending_cells.find({"ws": {"$in": need}}, {"_id": 0}):
            by_ws.setdefault(c["ws"], []).append(c)
        now = datetime.now(timezone.utc)
        ops = []
        for ws in touched:
            for scope, doc in S.window_docs(ws, by_ws.get(ws, []), by_ws.get(ws - S.WINDOW_MIN * 60, [])).items():
                ops.append(ReplaceOne({"_id": S.doc_id(ws, scope)},
                                      {**doc, "batch_id": batch_id, "updated_at": now,
                                       "replay": {"day": args.day, "speed": args.speed}}, upsert=True))
        db.trending.bulk_write(ops, ordered=False)
    t_done = time.time()
    newest = max((r["last_emit_ms"] for r in rows if r["last_emit_ms"]), default=None)
    rec = {"batch_id": batch_id, "rows": len(rows), "windows": len({r["ws"] for r in rows}),
           "collect_ms": round((t_collect - t_start) * 1000), "mongo_ms": round((t_done - t_collect) * 1000),
           "done_at_ms": round(t_done * 1000)}
    if newest:
        # Do tre cua su kien MOI NHAT trong batch: tu luc replayer ghi file den luc ghi MongoDB xong.
        # Su kien cu nhat trong batch cho them toi da 1 chu ky trigger + 1 giay (do min cua file) -> can tren.
        lat = t_done - newest / 1000
        rec.update({"newest_emit_ms": newest, "latency_s": round(lat, 3),
                    "latency_bound_s": round(lat + args.trigger + 1, 3)})
        state["latencies"].append(lat)
    state["n_batches"] += 1
    batches_log.write(json.dumps(rec) + "\n")
    batches_log.flush()
    L = state["latencies"][-20:]
    lat_doc = ({"last": round(L[-1], 2), "bound_last": round(L[-1] + args.trigger + 1, 2),
                "p50": round(statistics.median(L), 2),
                "p95": round(sorted(L)[max(0, int(round(0.95 * len(L))) - 1)], 2), "max": round(max(L), 2),
                "n": len(L)} if L else None)
    # newest_emit / data_batch_id chi doi khi batch co du lieu (10d do do tre su kien -> API theo cap nay)
    extra = {"newest_emit": datetime.fromtimestamp(newest / 1000, timezone.utc), "data_batch_id": batch_id} if newest else {}
    set_status(query_id=state["query_id"], last_batch_id=batch_id, n_batches=state["n_batches"],
               batch_rows=len(rows), latency_s=lat_doc, **extra)


class Progress(StreamingQueryListener):
    """Moi lan tien do: watermark, max ts (dong ho mo phong), toc do, so dong bi bo theo tung stateOperator."""

    def onQueryStarted(self, event):
        pass

    def onQueryProgress(self, event):
        p = json.loads(event.progress.json)
        progress_log.write(json.dumps(p, ensure_ascii=False) + "\n")
        progress_log.flush()
        ops = p.get("stateOperators") or []
        for op in ops:
            name = op.get("operatorName", "?")
            state["dropped"][name] = state["dropped"].get(name, 0) + (op.get("numRowsDroppedByWatermark") or 0)
        et = p.get("eventTime") or {}
        kw = {"progress_batch_id": p["batchId"], "dropped_by_watermark": dict(state["dropped"]),
              "state_rows": {op.get("operatorName", "?"): op.get("numRowsTotal") for op in ops}}
        if p.get("numInputRows"):
            # toc do chi lay tu batch co du lieu (batch rong khi cho / sau khi phat xong cho ra 0)
            kw.update({"input_rows": p["numInputRows"], "input_rows_per_s": round(p.get("inputRowsPerSecond") or 0, 1),
                       "processed_rows_per_s": round(p.get("processedRowsPerSecond") or 0, 1),
                       "batch_ms": (p.get("durationMs") or {}).get("triggerExecution")})
        if et.get("watermark"):
            kw["watermark"] = datetime.fromisoformat(et["watermark"].replace("Z", "+00:00"))
        if et.get("max"):
            kw["sim_now"] = datetime.fromisoformat(et["max"].replace("Z", "+00:00"))
        set_status(**kw)

    def onQueryIdle(self, event):
        pass

    def onQueryTerminated(self, event):
        pass


spark.streams.addListener(Progress())
query = (cells.writeStream.outputMode("update").foreachBatch(sink)
         .option("checkpointLocation", SP.uri(SP.checkpoint))
         .trigger(processingTime=f"{args.trigger} seconds")
         .queryName(f"trending_{args.run_id}").start())
state["query_id"] = str(query.id)
fs.put(SP.checkpoint_conf, json.dumps(CONF).encode())
set_status(**status_base, state="đang chạy", query_id=state["query_id"],
           started_at=datetime.now(timezone.utc), stopped_at=None)
print(f"[10] luong {query.id} dang chay: trigger {args.trigger}s, {args.cores} core, {args.partitions} partition. "
      f"Spark UI http://localhost:4041", flush=True)

done_file = os.path.join(run_dir, "DONE")
final_wm = hi + timedelta(minutes=S.WINDOW_MIN - S.SLIDE_MIN)      # cua so cuoi co du lieu ket thuc truoc moc nay
try:
    while query.isActive:
        query.awaitTermination(2)
        if os.path.exists(SP.stop_file):
            print("[10] gap file STOP, dung luong sau batch dang chay", flush=True)
            break
        if args.exit_when_done and os.path.exists(done_file):
            query.processAllAvailable()
            st = db.stream_status.find_one({"_id": "current"}, {"watermark": 1}) or {}
            wm = st.get("watermark")
            if wm and wm.replace(tzinfo=timezone.utc) >= final_wm:
                time.sleep(args.trigger)
                print(f"[10] replayer xong, watermark {wm:%Y-%m-%d %H:%M} UTC qua moi cua so: dung", flush=True)
                break
finally:
    err = query.exception()                 # query loi (vd tuy chon sai) -> thoat ma 1 de 10c / 10d biet
    query.stop()
    set_status(state="đã dừng", stopped_at=datetime.now(timezone.utc), error=str(err)[:500] if err else None)
    batches_log.close()
    progress_log.close()
    spark.stop()
print(f"[10] da dung sau {state['n_batches']} batch co ghi", flush=True)
if err:
    sys.exit(f"[10] query loi: {str(err)[:300]}")
