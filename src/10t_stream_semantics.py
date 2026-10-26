"""
10t_stream_semantics.py - Bai thu nho ve ngu nghia cua query luong (buoc 10, D18), chay Spark local.

Dung dung stream_query() cua 10_stream.py, dua tung file nho vao thu muc nguon roi cho xu ly xong, de tra loi:
  1. Phep loc event_type dat ngay sau withWatermark co bi optimizer day xuong DUOI EventTimeWatermark khong
     (neu co, tick bi loc truoc khi tinh watermark -> watermark khong tien)? Bang chung: so dong doc vao o F1
     (7 neu tick duoc doc) va watermark sau F3 (chi co tick).
  2. dropDuplicatesWithinWatermark co tu bo dong co ts < watermark khong (truoc khi den phep tong hop)?
  3. numRowsDroppedByWatermark cua tung stateOperator (khu trung, tong hop) moi batch.
  4. Su kien tre qua watermark nhung con cua so dang mo: duoc dem vao cua so mo hay bi bo ca?

Kich ban (1 user, 1 mon, cua so 60/15 phut, watermark 10 phut):
  F1: cook id 1..6 luc 10:00 ... 10:25, tick 10:30         -> watermark 10:20
  F2: id 101 luc 10:15 (tre, < watermark), id 102 luc 10:25 (>= watermark),
      gui lap id 6 (10:25, >= watermark), gui lap id 1 (10:00, < watermark)
  F3: chi 1 tick luc 11:30                                  -> watermark 11:20 neu tick qua duoc EventTimeWatermark
  F4: id 103 luc 11:25, id 104 luc 10:50 (< watermark 11:20; cua so [10:00,11:00) da dong, [10:30,11:30) con mo)
Hai bien the: loc truoc khu trung (filter_before_dedup=True) va loc sau khu trung (mac dinh cua 10_stream.py).

Dau ra : data/output/stream_semantics_report.json, in ket qua tung bien the
Chay   : python src/10t_stream_semantics.py   (luon chay local, ~1 phut; khong chay cung luc job khac)
"""
import json
import os
import shutil
import sys
import time
from datetime import datetime

from pyspark.sql import Row

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, get_spark  # noqa: E402
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
spark = get_spark("10t_stream_semantics", local=True, conf={"spark.sql.shuffle.partitions": "2"})
P = Paths(local=True)
BASE = os.path.join(S.PROJECT_DIR, "data", "hdfs_local", "stream_semantics")
users = spark.createDataFrame([Row(user_id=1, region="Bắc")])


def ev(eid, hm, kind="cook"):
    e = {"event_id": eid, "event_type": kind, "ts": f"2026-09-27T{hm}:00.000+07:00",
         "emit_ts": "2026-09-27T03:00:00.000+00:00"}
    if kind != "tick":
        e.update({"user_id": 1, "food_id": 10, "meal_slot": "sáng", "session_id": 1})
    return e


FILES = [
    ("F1", [ev(i + 1, f"10:{5 * i:02d}") for i in range(6)] + [ev(-1, "10:30", "tick")]),
    ("F2", [ev(101, "10:15"), ev(102, "10:25"), ev(6, "10:25"), ev(1, "10:00")]),
    ("F3", [ev(-2, "11:30", "tick")]),
    ("F4", [ev(103, "11:25"), ev(104, "10:50")]),
]


def run(variant, filter_before_dedup):
    root = os.path.join(BASE, variant)
    shutil.rmtree(root, ignore_errors=True)
    src, ck = os.path.join(root, "in"), os.path.join(root, "ck")
    os.makedirs(src)
    stream = spark.readStream.schema(S.EVENT_SCHEMA).json(f"file://{src}")
    q_df = S.stream_query(stream, users, filter_before_dedup=filter_before_dedup)
    latest = {}

    def sink(df, bid):
        for r in df.collect():
            latest[(r["ws"], r["food_id"])] = r["cooks"]

    q = (q_df.writeStream.outputMode("update").foreachBatch(sink).option("checkpointLocation", f"file://{ck}")
         .trigger(processingTime="500 milliseconds").start())
    steps = []
    for name, evs in FILES:
        before = len(q.recentProgress)
        with open(os.path.join(src, f"{name}.json"), "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in evs))
        q.processAllAvailable()
        time.sleep(2.0)                       # cho them batch khong du lieu (watermark moi duoc ap dung)
        for p in q.recentProgress[before:]:
            p = json.loads(p.json) if hasattr(p, "json") else p
            ops = [{"operator": o.get("operatorName"), "dropped": o.get("numRowsDroppedByWatermark"),
                    "state_rows": o.get("numRowsTotal")} for o in p.get("stateOperators", [])]
            steps.append({"after_file": name, "batch": p["batchId"], "input_rows": p["numInputRows"],
                          "watermark": p.get("eventTime", {}).get("watermark"), "operators": ops})
    q.stop()
    counts = {datetime.fromtimestamp(ws, S.VN).strftime("%H:%M"): c for (ws, _), c in sorted(latest.items())}
    # Tick co qua EventTimeWatermark khong: so dong doc vao o F1 va watermark sau F3 (11:20 = 04:20 UTC)
    wm_f3 = [b["watermark"] for b in steps if b["after_file"] == "F3"][-1]
    dropped = {}
    for b in steps:
        for o in b["operators"]:
            dropped[o["operator"]] = dropped.get(o["operator"], 0) + (o["dropped"] or 0)
    return {"filter_before_dedup": filter_before_dedup,
            "input_rows_f1": sum(b["input_rows"] for b in steps if b["after_file"] == "F1"),
            "watermark_after_f3": wm_f3, "tick_advances_watermark": wm_f3.startswith("2026-09-27T04:20"),
            "dropped_by_watermark_total": dropped, "final_cooks_by_window_start": counts, "batches": steps}


out = {"variants": {"loc_truoc_khu_trung": run("filter_before", True), "loc_sau_khu_trung": run("filter_after", False)}}
for name, r in out["variants"].items():
    print(f"\n== {name}: F1 doc {r['input_rows_f1']} dong (7 neu doc ca tick), watermark sau F3 {r['watermark_after_f3']}"
          f" -> tick day watermark: {r['tick_advances_watermark']}; bo theo watermark: {r['dropped_by_watermark_total']}")
    for b in r["batches"]:
        print(f"   sau {b['after_file']} batch {b['batch']}: {b['input_rows']} dong vao, watermark {b['watermark']}, "
              + "; ".join(f"{o['operator']} bo {o['dropped']} (state {o['state_rows']})" for o in b["operators"]))
    print("   luot nau cuoi cung theo cua so:", r["final_cooks_by_window_start"])
with open(os.path.join(P.output_local, "stream_semantics_report.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
spark.stop()
