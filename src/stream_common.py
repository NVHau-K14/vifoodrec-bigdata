"""
stream_common.py - Dung chung cho buoc 10 (Structured Streaming, D18).

  - hang so cua so / watermark, schema su kien JSON
  - stream_query()  : cac buoc cua query luong (10_stream.py va bai thu 10t dung chung)
  - aggregate()     : phep tong hop theo cua so x vung x mon (luong va dap an batch dung chung)
  - window_docs()   : tu cac o (vung, mon) cua 1 cua so -> doc trending cho 4 pham vi (sink va 10c dung chung)
  - FS              : ghi / doi ten / xoa file tren HDFS (WebHDFS) hoac thu muc local (--local)
  - mongo_db()      : database MongoDB cua luong

Chay truc tiep (scripts/10_stream.sh goi trong container jupyter):
  python src/stream_common.py reset [--local]     xoa /data/stream/{incoming,_staging,archive,checkpoint}, trending...
  python src/stream_common.py status [--local]    in trang thai luong (stream_status)
  python src/stream_common.py stop                tao file dung data/stream/STOP
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

from pyspark.sql import functions as F, types as T

PROJECT_DIR = os.getenv("PROJECT_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
VN = timezone(timedelta(hours=7))

WINDOW_MIN, SLIDE_MIN, WATERMARK_MIN = 60, 15, 10
WINDOW, SLIDE, WATERMARK = f"{WINDOW_MIN} minutes", f"{SLIDE_MIN} minutes", f"{WATERMARK_MIN} minutes"
TYPES = ["cook", "view", "favorite"]            # loai su kien duoc dem (rate, tick bi loc)
SLOTS = ["sáng", "trưa", "tối", "khuya"]
REGIONS = ["Bắc", "Trung", "Nam"]
SCOPES = ["all"] + REGIONS                      # "all" = toan quoc = tong 3 vung
TOP_N, RISING_N = 20, 5
FINAL_TICK_MIN = 75                             # tick cuoi: ts = gio ket thuc + 75 phut -> watermark vuot moi cua so
DEFAULT_DAY = "2026-09-27"                      # Chu nhat cuoi cua thang test (09/2026)

EVENT_SCHEMA = T.StructType([
    T.StructField("event_id", T.LongType()),
    T.StructField("user_id", T.IntegerType()),
    T.StructField("food_id", T.IntegerType()),
    T.StructField("event_type", T.StringType()),
    T.StructField("ts", T.TimestampType()),
    T.StructField("meal_slot", T.StringType()),
    T.StructField("session_id", T.LongType()),
    T.StructField("rating", T.FloatType()),
    T.StructField("emit_ts", T.TimestampType()),
])
CELL_COUNTS = ["cooks", "views", "favorites"] + [f"n_slot{i}" for i in range(len(SLOTS))]


# ---------------------------------------------------------------------------
# Duong dan
# ---------------------------------------------------------------------------
class StreamPaths:
    """HDFS /data/stream/... tren cum (theo ke hoach); data/hdfs_local/stream/... khi --local."""

    def __init__(self, local=False):
        self.local = local
        self.root = os.path.join(PROJECT_DIR, "data", "hdfs_local", "stream") if local else "/data/stream"
        for sub in ("incoming", "_staging", "archive", "checkpoint", "replay", "truth"):
            setattr(self, sub.strip("_"), f"{self.root}/{sub}")
        self.checkpoint_conf = f"{self.root}/checkpoint_conf.json"
        # tren may (mount vao container): file phat lai, file dung, nhat ky tung lan chay
        self.work = os.path.join(PROJECT_DIR, "data", "stream")
        self.stop_file = os.path.join(self.work, "STOP")
        self.runs = os.path.join(self.work, "runs")

    def uri(self, path):
        """Duong dan cho Spark doc / ghi."""
        if self.local:
            return f"file://{path}"
        return f"{os.getenv('HDFS_URL', 'hdfs://namenode:8020')}{path}"

    def replay_file(self, day, days=1):
        return os.path.join(self.work, f"replay_{day}{'' if days == 1 else f'_{days}d'}.jsonl.gz")

    def run_dir(self, run_id):
        d = os.path.join(self.runs, run_id)
        os.makedirs(d, exist_ok=True)
        return d


# ---------------------------------------------------------------------------
# Query luong va phep tong hop
# ---------------------------------------------------------------------------
def aggregate(df):
    """So dem TUYET DOI theo (cua so 60 phut truot 15 phut, vung, mon). Dung chung cho luong va dap an batch."""
    et = F.col("event_type")
    slot_counts = [F.sum((F.col("meal_slot") == s).cast("int")).alias(f"n_slot{i}") for i, s in enumerate(SLOTS)]
    return (df.groupBy(F.window("ts", WINDOW, SLIDE).alias("w"), "region", "food_id")
              .agg(F.sum((et == "cook").cast("int")).alias("cooks"),
                   F.sum((et == "view").cast("int")).alias("views"),
                   F.sum((et == "favorite").cast("int")).alias("favorites"),
                   *slot_counts,
                   F.max("emit_ts").alias("last_emit"))
              .select(F.col("w.start").cast("long").alias("ws"), F.col("w.end").cast("long").alias("we"),
                      "region", "food_id", *CELL_COUNTS,
                      (F.col("last_emit").cast("double") * 1000).cast("long").alias("last_emit_ms")))


def stream_query(events, users, filter_before_dedup=False):
    """
    events: DataFrame luong (EVENT_SCHEMA). users: bang tinh (user_id, region).
    withWatermark -> khu trung event_id trong watermark -> loc cook/view/favorite -> join users -> tong hop.
    Tick (khong co user, khong duoc dem) phai di qua EventTimeWatermark de watermark tien. Bai thu 10t (D18):
    loc ngay sau withWatermark thi optimizer day phep loc (khong dung cot ts) xuong DUOI EventTimeWatermark,
    tick bi loai truoc khi tinh watermark -> watermark dung yen. Khu trung (stateful) chan viec day xuong,
    nen loc dat sau khu trung. filter_before_dedup=True chi de tai hien loi trong 10t.
    """
    w = events.withWatermark("ts", WATERMARK)
    keep = F.col("event_type").isin(TYPES)
    if filter_before_dedup:
        d = w.filter(keep).dropDuplicatesWithinWatermark(["event_id"])
    else:
        d = w.dropDuplicatesWithinWatermark(["event_id"]).filter(keep)
    j = d.join(F.broadcast(users.select("user_id", "region")), "user_id")
    return aggregate(j)


# ---------------------------------------------------------------------------
# Tu o -> doc trending (sink va 10c dung chung de so khop dung tung truong)
# ---------------------------------------------------------------------------
def rank_key(it):
    return (-it["cooks"], -it["views"], it["food_id"])


def window_docs(ws, cells, prev_cells):
    """
    ws: epoch giay bat dau cua so. cells / prev_cells: list dict {region, food_id, cooks, views, favorites, n_slot0..3}
    cua cua so nay va cua so [ws - 60, ws) (khong chong lan, de tinh "tang nhanh").
    Tra ve {scope: doc} (chua co _id, batch_id, updated_at).
    """
    out = {}
    for scope in SCOPES:
        regs = REGIONS if scope == "all" else [scope]
        agg, prev, slots = {}, {}, [0] * len(SLOTS)
        for c in cells:
            if c["region"] not in regs:
                continue
            a = agg.setdefault(c["food_id"], {"food_id": c["food_id"], "cooks": 0, "views": 0, "favorites": 0})
            for k in ("cooks", "views", "favorites"):
                a[k] += c[k]
            for i in range(len(SLOTS)):
                slots[i] += c[f"n_slot{i}"]
        for c in prev_cells:
            if c["region"] in regs:
                prev[c["food_id"]] = prev.get(c["food_id"], 0) + c["cooks"]
        items = sorted(agg.values(), key=rank_key)
        top = [{**it, "rank": r + 1, "prev_cooks": prev.get(it["food_id"], 0)} for r, it in enumerate(items[:TOP_N])]
        rising = sorted(({"food_id": f, "cooks": it["cooks"], "prev_cooks": prev.get(f, 0),
                          "delta": it["cooks"] - prev.get(f, 0)} for f, it in agg.items()),
                        key=lambda x: (-x["delta"], -x["cooks"], x["food_id"]))
        rising = [x for x in rising if x["delta"] > 0][:RISING_N]
        out[scope] = {
            "window_start": datetime.fromtimestamp(ws, timezone.utc),
            "window_end": datetime.fromtimestamp(ws + WINDOW_MIN * 60, timezone.utc),
            "scope": scope,
            "meal_slot": SLOTS[max(range(len(SLOTS)), key=lambda i: slots[i])] if any(slots) else None,
            "total_cooks": sum(it["cooks"] for it in items),
            "total_views": sum(it["views"] for it in items),
            "total_favorites": sum(it["favorites"] for it in items),
            "n_dishes": sum(1 for it in items if it["cooks"] > 0),
            "items": top,
            "rising": rising,
        }
    return out


def doc_id(ws, scope):
    return f"{datetime.fromtimestamp(ws, VN):%Y-%m-%dT%H:%M}|{scope}"


def cell_id(ws, region, food_id):
    return f"{ws}|{region}|{food_id}"


# ---------------------------------------------------------------------------
# Thoi gian mo phong
# ---------------------------------------------------------------------------
def sim_bounds(day, t_from, t_to):
    """'2026-09-27', '06:00', '24:00' -> (datetime +07:00, datetime +07:00). 24:00 = 00:00 ngay hom sau."""
    d0 = datetime.fromisoformat(day).replace(tzinfo=VN)

    def at(hm):
        h, m = (int(x) for x in hm.split(":"))
        return d0 + timedelta(hours=h, minutes=m)
    return at(t_from), at(t_to)


def iso(dt):
    return dt.astimezone(VN).isoformat(timespec="milliseconds")


# ---------------------------------------------------------------------------
# File: HDFS qua WebHDFS (replayer khong dung Spark) hoac thu muc local
# ---------------------------------------------------------------------------
class FS:
    def __init__(self, local=False):
        self.local = local
        self.web = os.getenv("WEBHDFS_URL", "http://namenode:9870/webhdfs/v1")
        self.user = os.getenv("HDFS_USER", "jovyan")
        if not local:
            import requests
            self.http = requests.Session()

    def _url(self, path, op, **kw):
        q = "&".join([f"op={op}", f"user.name={self.user}"] + [f"{k}={v}" for k, v in kw.items()])
        return f"{self.web}{path}?{q}"

    def mkdirs(self, path):
        if self.local:
            os.makedirs(path, exist_ok=True)
        else:
            self.http.put(self._url(path, "MKDIRS")).raise_for_status()

    def put(self, path, data: bytes):
        if self.local:
            with open(path, "wb") as fh:
                fh.write(data)
            return
        r = self.http.put(self._url(path, "CREATE", overwrite="true", replication=2), allow_redirects=False)
        r.raise_for_status()
        self.http.put(r.headers["Location"], data=data).raise_for_status()

    def rename(self, src, dst):
        """Doi ten nguyen tu: file source cua Spark chi thay file da ghi xong."""
        if self.local:
            os.replace(src, dst)
            return
        r = self.http.put(self._url(src, "RENAME", destination=dst))
        r.raise_for_status()
        if not r.json().get("boolean"):
            raise RuntimeError(f"RENAME {src} -> {dst} that bai")

    def delete(self, path):
        if self.local:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            return
        self.http.delete(self._url(path, "DELETE", recursive="true")).raise_for_status()

    def exists(self, path):
        if self.local:
            return os.path.exists(path)
        return self.http.get(self._url(path, "GETFILESTATUS")).status_code == 200

    def read(self, path):
        if self.local:
            with open(path, "rb") as fh:
                return fh.read()
        r = self.http.get(self._url(path, "OPEN"))
        r.raise_for_status()
        return r.content


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
def mongo_db(local=False):
    from pymongo import MongoClient
    name = "vifood_local" if local else os.getenv("MONGO_DB", "vifood")
    return MongoClient(os.environ["MONGO_URI"])[name]


STREAM_COLLECTIONS = ["trending", "trending_cells", "stream_status"]


def reset(local=False):
    """Xoa du lieu cua luong: thu muc tren HDFS (ca checkpoint) va 3 collection. Giu replay/ va truth/."""
    sp, fs = StreamPaths(local), FS(local)
    for sub in (sp.incoming, sp.staging, sp.archive, sp.checkpoint, sp.checkpoint_conf):
        fs.delete(sub)
    for sub in (sp.incoming, sp.staging, sp.archive):
        fs.mkdirs(sub)
    db = mongo_db(local)
    for c in STREAM_COLLECTIONS:
        db[c].delete_many({})
    if os.path.exists(sp.stop_file):
        os.remove(sp.stop_file)
    print(f"[10] reset: {sp.root}/{{incoming,_staging,archive,checkpoint}}, {', '.join(STREAM_COLLECTIONS)}", flush=True)


def run_pair(run_id, common, stream_extra=(), replay_extra=(), replay_first=False, on_tick=None, timeout=3600):
    """
    10c / 10d: chay 10_stream.py (--exit-when-done) va 10b_replayer.py thanh tien trinh con, cho ca hai xong.
    common: tham so chung (--day, --from, --to, --speed, --late ...). replay_first: ghi het file truoc roi moi bat luong
    (do thong luong). on_tick(): goi moi 0,5 giay khi luong dang chay (vd hoi API de do do tre).
    Log: logs/stream/<run_id>_{stream,replayer}.log. Tra ve thoi gian (giay) cua tung tien trinh.
    """
    import subprocess
    import time
    logd = os.path.join(PROJECT_DIR, "logs", "stream")
    os.makedirs(logd, exist_ok=True)
    py = [sys.executable, "-u"]

    def start(script, extra, name):
        log = open(os.path.join(logd, f"{run_id}_{name}.log"), "w", encoding="utf-8")
        return subprocess.Popen(py + [f"src/{script}", "--run-id", run_id, *common, *extra], cwd=PROJECT_DIR,
                                stdout=log, stderr=subprocess.STDOUT), log

    t0, times = time.time(), {}
    if replay_first:
        pr, lr = start("10b_replayer.py", replay_extra, "replayer")
        if pr.wait() != 0:
            raise RuntimeError(f"replayer loi, xem logs/stream/{run_id}_replayer.log")
        times["replayer_s"] = round(time.time() - t0, 1)
    ps, ls = start("10_stream.py", ["--exit-when-done", *stream_extra], "stream")
    slog = os.path.join(logd, f"{run_id}_stream.log")
    while "dang chay" not in open(slog, encoding="utf-8", errors="replace").read():
        if ps.poll() is not None:
            raise RuntimeError(f"luong dung som, xem {slog}")
        time.sleep(0.5)
    t_stream = time.time()
    if not replay_first:
        pr, lr = start("10b_replayer.py", replay_extra, "replayer")
    while ps.poll() is None:
        if on_tick:
            on_tick()
        if time.time() - t0 > timeout:
            ps.kill()
            pr.kill()
            raise RuntimeError(f"qua {timeout}s, da dung {run_id}")
        time.sleep(0.5)
    if pr.wait() != 0 or ps.returncode != 0:
        raise RuntimeError(f"{run_id}: replayer {pr.returncode}, luong {ps.returncode}; xem logs/stream/")
    times["stream_s"] = round(time.time() - t_stream, 1)
    for f in (ls, lr):
        f.close()
    return times


def status(local=False):
    st = mongo_db(local).stream_status.find_one({"_id": "current"})
    if not st:
        print("[10] chua chay (stream_status trong)")
        return
    st.pop("_id", None)
    print(json.dumps(st, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["reset", "status", "stop"])
    ap.add_argument("--local", action="store_true")
    a = ap.parse_args()
    if a.cmd == "reset":
        reset(a.local)
    elif a.cmd == "status":
        status(a.local)
    else:
        sp = StreamPaths(a.local)
        os.makedirs(sp.work, exist_ok=True)
        open(sp.stop_file, "w").close()
        print(f"[10] da tao {sp.stop_file}: replayer dung ngay, luong dung sau batch dang chay")
