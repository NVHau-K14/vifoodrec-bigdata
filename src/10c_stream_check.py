"""
10c_stream_check.py - Kiem tra ket qua Structured Streaming voi dap an batch (buoc 10, D18).

Chay 3 kich ban (moi kich ban: reset -> bat luong + replayer -> cho xong -> chup lai trending / trending_cells):
  s1  --late 0  khong tre, khong gui lap                 -> moi o va moi doc trending KHOP TUYET DOI dap an
  s2  --late 1  3% tre 1-8 phut + 0,2% gui lap           -> KHOP TUYET DOI (tre trong watermark van duoc dem,
                                                             ban lap bi khu)
  s3  --late 2  them 0,3% bi giu 20-40 phut (qua watermark) -> BAT DANG THUC: moi o khong vuot dap an; phan thieu cua
                                                             moi (cua so, vung) <= so su kien bi giu > 10 phut roi vao do
Dap an: Spark batch tren dung doan phat lai (HDFS /data/stream/replay/<ngay>), chi tinh ts trong [--from, --to),
cung ham stream_common.aggregate / window_docs voi luong.
Sau s3 (checkpoint con giu): doc state store bang spark.read.format("state-metadata" / "statestore")
o batch cuoi - 30 (khoang 21:30 gio mo phong), in vai dong trang thai cua phep khu trung va phep tong hop (de chup anh cho bao cao).

Dau vao : data/stream/replay_<ngay>.jsonl.gz, HDFS /data/stream/replay/<ngay>, /data/events/users (10a phai chay truoc)
Dau ra  : data/output/stream_report.json   khoa "checks" (giu khoa "bench" cua 10d)
          data/output/stream/statestore_sample.txt
Chay tren cum (tu may, xem CLAUDE.md; ~15 phut):
  python src/10c_stream_check.py                  # 3 kich ban, toc do 300, trigger 1 giay, 06:00-24:00
  python src/10c_stream_check.py --only s1
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, Timer, get_spark  # noqa: E402
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--day", default=S.DEFAULT_DAY)
ap.add_argument("--from", dest="t_from", default="06:00")
ap.add_argument("--to", dest="t_to", default="24:00")
ap.add_argument("--speed", default="300")
ap.add_argument("--only", default="", help="vd s1,s3")
args = ap.parse_args()

SCEN = [("s1", 0, "không trễ, không gửi lặp"),
        ("s2", 1, "3% trễ 1–8 phút, 0,2% gửi lặp"),
        ("s3", 2, "như s2, thêm 0,3% bị giữ 20–40 phút (quá watermark)")]
if args.only:
    SCEN = [s for s in SCEN if s[0] in args.only.split(",")]
SP, P, T = S.StreamPaths(), Paths(), Timer("10c")
db = S.mongo_db()
stamp = datetime.now().strftime("%m%d_%H%M%S")
runs = {}

# ---------------------------------------------------------------------------
# 1. Chay cac kich ban, chup lai ket qua
# ---------------------------------------------------------------------------
for name, late, desc in SCEN:
    T.mark(f"run_{name}")
    run_id = f"check_{name}_{stamp}"
    print(f"[10c] {name}: {desc} (run {run_id})", flush=True)
    S.reset()
    common = ["--day", args.day, "--from", args.t_from, "--to", args.t_to, "--speed", args.speed, "--late", str(late)]
    times = S.run_pair(run_id, common)
    for c in ("trending_cells", "trending"):
        db[c].aggregate([{"$match": {}}, {"$out": f"chk_{name}_{c}"}])
    st = db.stream_status.find_one({"_id": "current"})
    rep = json.load(open(os.path.join(SP.run_dir(run_id), "replayer.json"), encoding="utf-8"))
    batches = [json.loads(x) for x in open(os.path.join(SP.run_dir(run_id), "batches.jsonl"), encoding="utf-8")]
    progress = [json.loads(x) for x in open(os.path.join(SP.run_dir(run_id), "progress.jsonl"), encoding="utf-8")]
    runs[name] = {"late": late, "desc": desc, "run_id": run_id, "times": times, "replayer": rep, "status": st,
                  "batches": batches, "progress": progress}
    print(f"[10c] {name}: {times}, {st.get('n_batches')} batch co ghi, bo theo watermark {st.get('dropped_by_watermark')}",
          flush=True)

# ---------------------------------------------------------------------------
# 2. Dap an batch (Spark tren cum, sau khi luong da dung)
# ---------------------------------------------------------------------------
T.mark("truth")
spark = get_spark("10c_stream_check")
lo, hi = S.sim_bounds(args.day, args.t_from, args.t_to)
users = spark.read.parquet(f"{P.events}/users").select("user_id", "region")
ev = (spark.read.parquet(SP.uri(f"{SP.replay}/{args.day}"))
      .where((F.col("ts") >= F.lit(lo.isoformat()).cast("timestamp")) & (F.col("ts") < F.lit(hi.isoformat()).cast("timestamp"))))
truth_rows = S.aggregate(ev.where(F.col("event_type").isin(S.TYPES)).join(users, "user_id")
                           .withColumn("emit_ts", F.lit(None).cast("timestamp"))).collect()
truth = {(r["ws"], r["region"], r["food_id"]): tuple(r[k] for k in S.CELL_COUNTS) for r in truth_rows}
region_of = {r["user_id"]: r["region"] for r in users.collect()}
print(f"[10c] dap an: {len(truth):,} o, {ev.count():,} su kien trong [{args.t_from}, {args.t_to})", flush=True)


def docs_from(cells_by_key):
    by_ws = defaultdict(list)
    for (ws, region, food), v in cells_by_key.items():
        by_ws[ws].append({"region": region, "food_id": food, **dict(zip(S.CELL_COUNTS, v))})
    out = {}
    for ws, cs in by_ws.items():
        for scope, d in S.window_docs(ws, cs, by_ws.get(ws - S.WINDOW_MIN * 60, [])).items():
            out[S.doc_id(ws, scope)] = d
    return out


DOC_KEYS = ["scope", "meal_slot", "total_cooks", "total_views", "total_favorites", "n_dishes", "items", "rising"]
truth_docs = docs_from(truth)


def windows_of(ts_iso):
    """Cac cua so (epoch giay bat dau) chua thoi diem ts."""
    t = int(datetime.fromisoformat(ts_iso).timestamp())
    first = (t - S.WINDOW_MIN * 60) // (S.SLIDE_MIN * 60) * (S.SLIDE_MIN * 60) + S.SLIDE_MIN * 60
    return [w for w in range(first, t + 1, S.SLIDE_MIN * 60) if w <= t < w + S.WINDOW_MIN * 60]


# ---------------------------------------------------------------------------
# 3. So khop
# ---------------------------------------------------------------------------
T.mark("compare")
checks = {}
for name, r in runs.items():
    got = {(c["ws"], c["region"], c["food_id"]): tuple(c[k] for k in S.CELL_COUNTS)
           for c in db[f"chk_{name}_trending_cells"].find({}, {"_id": 0})}
    got_docs = {d["_id"]: d for d in db[f"chk_{name}_trending"].find()}
    extra = [k for k in got if k not in truth]
    over = [k for k, v in got.items() if k in truth and any(a > b for a, b in zip(v, truth[k]))]
    diff = [k for k in truth if got.get(k) != truth[k]]
    doc_diff = [i for i, d in truth_docs.items()
                if i not in got_docs or any(got_docs[i].get(k) != d.get(k) for k in DOC_KEYS)]
    c = {"desc": r["desc"], "late": r["late"], "truth_cells": len(truth), "stream_cells": len(got),
         "cells_differ": len(diff), "cells_extra": len(extra), "cells_over_truth": len(over),
         "truth_docs": len(truth_docs), "stream_docs": len(got_docs), "docs_differ": len(doc_diff),
         "events_replayed": r["replayer"]["events"], "late_within": r["replayer"]["late_within"],
         "duplicates_sent": r["replayer"]["duplicates"], "held_beyond_watermark": r["replayer"]["held_beyond"],
         "dropped_by_watermark": r["status"].get("dropped_by_watermark"),
         "batches_written": r["status"].get("n_batches"), "times_s": r["times"],
         "examples_differ": [list(k) + [list(truth[k]), list(got.get(k) or [])] for k in diff[:3]]}
    if r["late"] < 2:
        c["pass"] = not diff and not extra and not doc_diff
        c["rule"] = "khớp tuyệt đối từng ô và từng doc trending"
    else:
        # phan thieu theo (cua so, vung), tinh tren tong cook + view + favorite
        miss = defaultdict(int)
        for k, v in truth.items():
            g = got.get(k, (0,) * len(v))
            miss[(k[0], k[1])] += sum(v[:3]) - sum(g[:3])
        held = defaultdict(int)
        for h in r["replayer"]["held"]:
            if h["event_type"] in S.TYPES and h["user_id"] in region_of:
                for ws in windows_of(h["ts"]):
                    held[(ws, region_of[h["user_id"]])] += 1
        bad = [k for k, m in miss.items() if m > held.get(k, 0)]
        n_held = sum(1 for h in r["replayer"]["held"] if h["event_type"] in S.TYPES)
        after_end = sum(1 for h in r["replayer"]["held"] if h["event_type"] in S.TYPES
                        and datetime.fromisoformat(h["ts"]).timestamp() + h["delay_min"] * 60 >= hi.timestamp())
        c.update({"missing_events_total": sum(miss.values()), "held_counted_types": n_held,
                  "held_window_slots": sum(held.values()), "held_emitted_after_end": after_end,
                  "windows_missing_over_held": len(bad), "pass": not extra and not over and not bad,
                  "rule": "không ô nào vượt đáp án; phần thiếu của mỗi (cửa sổ, vùng) ≤ số sự kiện bị giữ > 10 phút "
                          "rơi vào đó"})
    # Watermark cua batch tinh tu batch truoc: batch nhan su kien tre toi (ts lon nhat trong batch - watermark).
    # Batch gom nhieu file (khi xu ly cham hon trigger) thi khoang nay > 10 phut + 1 file.
    gaps = []
    for p in r["progress"]:
        et = p.get("eventTime") or {}
        if p.get("numInputRows") and et.get("max") and et.get("watermark") and not et["watermark"].startswith("1970"):
            gaps.append((datetime.fromisoformat(et["max"].replace("Z", "+00:00"))
                         - datetime.fromisoformat(et["watermark"].replace("Z", "+00:00"))).total_seconds() / 60)
    gaps.sort()
    c["accept_window_min"] = {"n_batches": len(gaps), "p50": gaps[len(gaps) // 2] if gaps else None,
                              "max": gaps[-1] if gaps else None, "batches_ge_20": sum(1 for g in gaps if g >= 20),
                              "batches_ge_30": sum(1 for g in gaps if g >= 30)}
    checks[name] = c
    print(f"[10c] {name}: {'DAT' if c['pass'] else 'KHONG DAT'} - o lech {c['cells_differ']}, o thua {c['cells_extra']}, "
          f"doc lech {c['docs_differ']}" + (f", thieu {c['missing_events_total']} / giu {c['held_counted_types']} su kien"
                                            f" ({c['held_window_slots']} luot cua so)" if r["late"] == 2 else ""), flush=True)

for name in runs:
    for c in ("trending_cells", "trending"):
        db[f"chk_{name}_{c}"].drop()
rep_file = os.path.join(P.output_local, "stream_report.json")


def save(extra=None):
    report = json.load(open(rep_file, encoding="utf-8")) if os.path.exists(rep_file) else {}
    report["checks"] = {"generated_at": datetime.now().isoformat(timespec="seconds"), "day": args.day,
                        "from": args.t_from, "to": args.t_to, "speed": args.speed, "scenarios": checks,
                        "all_pass": all(c["pass"] for c in checks.values()), "timings_s": T.parts,
                        "total_seconds": T.total(), **(extra or {})}
    with open(rep_file, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)


T.mark()
save()                                     # ghi truoc buoc doc state store (buoc do loi cung khong mat ket qua)

# ---------------------------------------------------------------------------
# 4. State store cua kich ban cuoi (checkpoint con giu): in vai dong de chup anh
# ---------------------------------------------------------------------------
T.mark("statestore")
lines = []
if runs:
    # Executor doc state store phai goi StateStoreCoordinator tren driver; phien chua tung chay query luong thi
    # chua co endpoint nay (loi CANNOT_LOAD_STATE_STORE). spark.streams tao StreamingQueryManager -> dang ky coordinator.
    spark.streams.active
    ck = SP.uri(SP.checkpoint)
    meta = spark.read.format("state-metadata").load(ck)
    lines.append("== state-metadata ==\n" + meta._jdf.showString(20, 0, False))
    last = max(b["batch_id"] for b in runs[list(runs)[-1]]["batches"])
    mid = max(0, last - 30)      # state store chi giu 100 phien ban gan nhat (minBatchesToRetain)
    for op in meta.select("operatorId", "operatorName").distinct().orderBy("operatorId").collect():
        df = spark.read.format("statestore").option("operatorId", op["operatorId"]).option("batchId", mid).load(ck)
        lines.append(f"== statestore operatorId={op['operatorId']} ({op['operatorName']}), batchId={mid}: "
                     f"{df.count():,} dong ==\n" + df._jdf.showString(5, 0, False))
    os.makedirs(os.path.join(P.output_local, "stream"), exist_ok=True)
    with open(os.path.join(P.output_local, "stream", "statestore_sample.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines), flush=True)
T.mark()
save({"statestore_batch_id": mid if runs else None})
print(f"[10c] xong sau {T.total()}s: {'MOI KICH BAN DAT' if all(c['pass'] for c in checks.values()) else 'CO KICH BAN KHONG DAT'}",
      flush=True)
spark.stop()
