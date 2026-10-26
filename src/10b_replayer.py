"""
10b_replayer.py - Phat lai su kien MO PHONG theo dong ho mo phong cho Structured Streaming (buoc 10, D18).

Python thuong (khong dung Spark), chay trong container jupyter. Moi chu ky ghi 1 file JSON Lines gom cac
su kien den han trong khoang dong ho mo phong vua troi qua, gan emit_ts = gio that luc ghi. Ghi vao
/data/stream/_staging qua WebHDFS roi RENAME sang /data/stream/incoming (nguyen tu: Spark chi thay file da xong).

  - Toc do: --speed 60 = 1 giay that / 1 phut mo phong (moi giay 1 file); --speed max: ghi het, moi file
    --chunk-min phut mo phong (do thong luong).
  - Den tre (--late, seed co dinh):
        0  khong tre, khong gui lap
        1  3% su kien tre 1-8 phut (trong watermark 10 phut) + 0,2% gui lap cung event_id (tre them 0-3 phut)
        2  nhu 1, them 0,3% su kien bi giu 20-40 phut (qua watermark)
  - Tick: phut mo phong nao khong co su kien thi phat 1 su kien "tick" (khong duoc dem) de watermark van tien;
    cuoi cung phat tick ts = --to + 75 phut de watermark vuot moi cua so -> cua so cuoi duoc chot.
  - File data/stream/STOP: dung ngay.

Dau vao : data/stream/replay_<ngay>[_<n>d].jsonl.gz       (10a_stream_prep.py)
Dau ra  : HDFS /data/stream/incoming/part-<so>.jsonl
          data/stream/runs/<run_id>/replayer.json            cau hinh, so dem, danh sach su kien bi giu > 10 phut
          data/stream/runs/<run_id>/DONE                     da phat xong (ke ca tick cuoi)

Chay (thuong do scripts/10_stream.sh hoac 10c/10d goi):
  python src/10b_replayer.py --run-id demo --from 16:00 --speed 60
  python src/10b_replayer.py --run-id t1 --speed max --chunk-min 720 --days 7 --day 2026-09-21
"""
import argparse
import gzip
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stream_common as S  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ap = argparse.ArgumentParser()
ap.add_argument("--run-id", required=True)
ap.add_argument("--day", default=S.DEFAULT_DAY)
ap.add_argument("--days", type=int, default=1)
ap.add_argument("--from", dest="t_from", default="06:00")
ap.add_argument("--to", dest="t_to", default="24:00", help="gio ket thuc cua ngay cuoi")
ap.add_argument("--speed", default="60", help="so lan nhanh hon thoi gian that, hoac 'max'")
ap.add_argument("--chunk-min", type=float, default=1.0, help="--speed max: so phut mo phong moi file")
ap.add_argument("--late", type=int, default=1, choices=[0, 1, 2])
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--local", action="store_true")
args = ap.parse_args()

SP, fs = S.StreamPaths(args.local), S.FS(args.local)
run_dir = SP.run_dir(args.run_id)
# [--from cua ngay dau, --to cua ngay cuoi); cung cach tinh voi 10_stream.py
lo, hi = S.sim_bounds(args.day, args.t_from, args.t_to)
hi += timedelta(days=args.days - 1)
MAX = args.speed == "max"
speed = None if MAX else float(args.speed)
step = timedelta(minutes=args.chunk_min) if MAX else timedelta(seconds=speed)   # khoang mo phong moi file
period = 0.0 if MAX else 1.0                                                     # giay that giua 2 file

# ---------------------------------------------------------------------------
# Doc doan phat lai, gan do tre / gui lap, them tick
# ---------------------------------------------------------------------------
t_load = time.time()
src = SP.replay_file(args.day, args.days)
events = []
with gzip.open(src, "rt", encoding="utf-8") as fh:
    for line in fh:
        ev = json.loads(line)
        ts = datetime.fromisoformat(ev["ts"])
        if lo <= ts < hi:
            events.append((ts, ev))
rng = random.Random(args.seed)
items, held, n_within, n_dup = [], [], 0, 0      # items: (gio phat mo phong, thu tu, su kien)
for i, (ts, ev) in enumerate(events):
    r, delay = rng.random(), 0.0
    if args.late >= 1 and r < 0.03:
        delay, n_within = rng.uniform(1, 8), n_within + 1
    elif args.late >= 2 and r < 0.033:
        delay = rng.uniform(20, 40)
        held.append({**{k: ev[k] for k in ("event_id", "user_id", "food_id", "event_type", "ts")},
                     "delay_min": round(delay, 2)})
    emit = ts + timedelta(minutes=delay)
    items.append((emit, i, ev))
    if args.late >= 1 and rng.random() < 0.002:
        n_dup += 1
        items.append((emit + timedelta(minutes=rng.uniform(0, 3)), i, ev))
# tick cho moi phut mo phong khong co su kien nao duoc phat
busy = {int((e - lo).total_seconds() // 60) for e, _, _ in items}
n_min = int((hi - lo).total_seconds() // 60)
ticks = 0
for m in range(n_min):
    if m not in busy:
        t = lo + timedelta(minutes=m)
        items.append((t, -1, {"event_id": -(m + 1), "event_type": "tick", "ts": S.iso(t)}))
        ticks += 1
items.sort(key=lambda x: (x[0], x[1]))
final_tick = {"event_id": -(n_min + 1), "event_type": "tick", "ts": S.iso(hi + timedelta(minutes=S.FINAL_TICK_MIN))}
print(f"[10b] {len(events):,} su kien trong [{S.iso(lo)}, {S.iso(hi)}), tre trong watermark {n_within}, "
      f"bi giu qua watermark {len(held)}, gui lap {n_dup}, tick {ticks} (+1 tick cuoi); doc {time.time() - t_load:.1f}s",
      flush=True)

# ---------------------------------------------------------------------------
# Phat theo dong ho mo phong
# ---------------------------------------------------------------------------
for d in (SP.incoming, SP.staging):
    fs.mkdirs(d)
seq, idx, clock, behind_max, n_rows = 0, 0, lo, 0.0, 0
info = {"run_id": args.run_id, "day": args.day, "days": args.days, "from": S.iso(lo), "to": S.iso(hi),
        "speed": args.speed, "chunk_min": args.chunk_min if MAX else None, "late": args.late, "seed": args.seed,
        "events": len(events), "late_within": n_within, "held_beyond": len(held), "duplicates": n_dup,
        "ticks": ticks + 1, "source": os.path.relpath(src, S.PROJECT_DIR).replace("\\", "/")}


def write(evs):
    """Ghi 1 file: staging -> rename sang incoming."""
    global seq, n_rows
    now = S.iso(datetime.now(timezone.utc))
    body = "".join(json.dumps({**e, "emit_ts": now}, ensure_ascii=False) + "\n" for e in evs).encode("utf-8")
    name = f"part-{seq:06d}.jsonl"
    fs.put(f"{SP.staging}/{name}", body)
    fs.rename(f"{SP.staging}/{name}", f"{SP.incoming}/{name}")
    seq, n_rows = seq + 1, n_rows + len(evs)


t0 = time.time()
info["started_at"] = S.iso(datetime.now(timezone.utc))
stopped = False
while idx < len(items):
    if os.path.exists(SP.stop_file):
        stopped = True
        print("[10b] gap file STOP, dung", flush=True)
        break
    clock += step
    batch = []
    while idx < len(items) and items[idx][0] < clock:
        batch.append(items[idx][2])
        idx += 1
    if batch:
        write(batch)
    if period:
        k = (clock - lo) / step
        wait = t0 + k * period - time.time()
        behind_max = max(behind_max, -wait)
        if wait > 0:
            time.sleep(wait)
    if seq and seq % 60 == 0 and batch:
        print(f"[10b] gio mo phong {clock.astimezone(S.VN):%H:%M}, {seq} file, {n_rows:,} dong", flush=True)
if not stopped:
    write([final_tick])
info.update({"finished_at": S.iso(datetime.now(timezone.utc)), "real_seconds": round(time.time() - t0, 1),
             "files": seq, "rows_written": n_rows, "behind_schedule_max_s": round(behind_max, 3),
             "stopped": stopped, "held": held})
with open(os.path.join(run_dir, "replayer.json"), "w", encoding="utf-8") as fh:
    json.dump(info, fh, ensure_ascii=False, indent=1)
if not stopped:
    open(os.path.join(run_dir, "DONE"), "w").close()
print(f"[10b] xong: {seq} file, {n_rows:,} dong trong {info['real_seconds']}s "
      f"(cham nhat {behind_max:.2f}s so voi lich)", flush=True)
