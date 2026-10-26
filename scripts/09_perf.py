"""
09_perf.py - Do hieu nang Spark: so worker (1 / 2) x quy mo du lieu (10 / 50 / 100%) cho cac job 02-06 (D17).

Chay TREN MAY (Python chuan, khong can thu vien them), dieu khien cum Docker bang lenh docker:
  - bat / tat spark-worker-2, cho master (http://localhost:8080/json/) bao du so worker con song
  - chay tung job bang `docker exec jupyter python src/<job>.py` voi bien moi truong
        VIFOOD_DATA_ROOT=/perf/<muc>                      goc HDFS rieng, khong dung /data
        VIFOOD_OUTPUT_DIR=data/output/perf/<lan chay>     report rieng, khong ghi de data/output
        VIFOOD_RUN_TAG=<muc>|w<n>|r<k>                    gan vao ten ung dung tren History Server
  - doc History Server REST (http://localhost:18080/api/v1): thoi luong, stage, job group, executor
  - lay mau `docker stats` trong luc chay (dinh RAM, CPU cua worker va jupyter)

Ke hoach (D17): chuoi 04 -> 06f o 100%, 50%, 10% (1 va 2 worker), 1 lan;
  05 va 06b o 100% chay them 2 lan moi cau hinh (tong 3, lay trung vi); danh muc 02, 03, 06g o 1 va 2 worker.
  06b, 06c, 06e, 06f, 06g chay voi --fixed (fit 1 lan voi tham so da chon).

Dau ra : data/output/perf_runs.jsonl   moi dong 1 lan chay (chay lai thi bo qua lan da co -> dung giua chung duoc)
         data/output/perf_report.json  tong hop: trung vi, min-max, speedup (theo job, theo muc), shuffle, spill
         data/output/perf/<lan chay>/  report cua tung lan chay (VIFOOD_OUTPUT_DIR)
         logs/perf/<lan chay>.log      stdout/stderr cua job

Cach chay (tu thu muc du an):
  python scripts/09_perf.py --plan                in danh sach lan chay va thoi gian du kien
  python scripts/09_perf.py                       chay toan bo ke hoach roi tong hop
  python scripts/09_perf.py --only s010:w2        chi chay cac lan khop muc[:wN[:job[:rK]]] (nhieu muc: dau phay)
  python scripts/09_perf.py --with-06b-quick      them 06b --quick o 100% (khi 06b --fixed 1 worker het bo nho)
  python scripts/09_perf.py --summarize           chi tong hop perf_report.json tu perf_runs.jsonl
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
PROJECT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(PROJECT, "data", "output")
RUNS_FILE = os.path.join(OUT, "perf_runs.jsonl")
REPORT_FILE = os.path.join(OUT, "perf_report.json")
LOG_DIR = os.path.join(PROJECT, "logs", "perf")
WORK = "/home/jovyan/work"
PYPATH = "/usr/local/spark/python/lib/py4j-0.10.9.9-src.zip:/usr/local/spark/python"
MASTER_JSON = "http://localhost:8080/json/"
HS = "http://localhost:18080/api/v1"
WORKER2 = "spark-worker-2"
STATS_CONTAINERS = ("spark-worker-1", "spark-worker-2", "jupyter", "namenode", "datanode1", "datanode2")

# job -> (script, tham so, report, thoi gian uoc tinh o 100% / 2 worker (giay), ten buoc)
JOBS = {
    "02": ("02_clean.py", [], "clean_report.json", 40, "02 Làm sạch"),
    "03": ("03_features.py", [], "features_report.json", 46, "03 Đặc trưng món"),
    "04": ("04_simulate.py", ["--scale", "{scale}"], "simulate_report.json", 543, "04 Sinh hành vi"),
    "05": ("05_analysis.py", [], "analysis_report.json", 104, "05 Phân tích hành vi"),
    "06a": ("06a_split.py", [], "model_split_report.json", 101, "06a Chia dữ liệu"),
    "06b": ("06b_als.py", ["--fixed"], "model_als_report.json", 565, "06b ALS + baseline"),
    "06c": ("06c_content.py", ["--fixed"], "model_content_report.json", 131, "06c Content"),
    "06d": ("06d_fpgrowth.py", [], "model_fpgrowth_report.json", 34, "06d FP-Growth"),
    "06e": ("06e_kmeans.py", ["--fixed"], "model_kmeans_report.json", 65, "06e K-means"),
    "06f": ("06f_hybrid.py", ["--fixed"], "model_hybrid_report.json", 95, "06f Hybrid"),
    "06g": ("06g_control.py", ["--fixed"], "model_control_report.json", 30, "06g Đối chứng"),
    # chi dung khi 06b --fixed o 100% / 1 worker het bo nho (D17)
    "06bq": ("06b_als.py", ["--quick"], "model_als_report.json", 300, "06b ALS (--quick)"),
}
CHAIN = ["04", "05", "06a", "06b", "06c", "06d", "06e", "06f"]
CATALOG = ["02", "03", "06g"]
SCALE_JOBS = ["04", "05", "06b"]  # job nang, dung cho speedup_by_scale
LEVELS = {"s010": 0.1, "s050": 0.5, "s100": 1.0, "catalog": None}
# Thoi gian o 10% / 2 worker do duoc khi chay thu (26/10); muc khac noi suy tuyen tinh theo ti le du lieu
EST_10 = {"04": 97, "05": 69, "06a": 48, "06b": 120, "06c": 84, "06d": 35, "06e": 36, "06f": 48, "06bq": 100}
W1_FACTOR = 1.5                 # uoc tinh: 1 worker cham ~1,5 lan (06b o 100%: 818 / ~565 giay)
OVERHEAD_S = 20                 # khoi dong JVM + cho History Server, moi lan chay
SWITCH_S = 30                   # bat / tat worker


def key_of(r):
    return f"{r['job']}_{r['level']}_w{r['workers']}_r{r['rep']}"


def build_plan(with_quick=False):
    runs = []

    def add(level, workers, jobs, rep=1):
        runs.extend({"level": level, "workers": workers, "job": j, "rep": rep} for j in jobs)

    add("catalog", 2, CATALOG)
    add("catalog", 1, CATALOG)
    add("s010", 2, CHAIN)
    add("s010", 1, CHAIN)
    add("s050", 2, CHAIN)
    add("s050", 1, CHAIN)                    # them sau (26/10) de duong 1 worker du 3 muc
    add("s100", 2, CHAIN)
    add("s100", 1, CHAIN)
    for rep in (2, 3):                       # xen ke 2 worker -> 1 worker
        for w in (2, 1):
            add("s100", w, ["05", "06b"], rep)
    if with_quick:
        for rep in (1, 2, 3):
            for w in (2, 1):
                add("s100", w, ["06bq"], rep)
    return runs


def estimate(r):
    t100, x = JOBS[r["job"]][3], LEVELS[r["level"]]
    t = t100 if x is None or r["job"] not in EST_10 else EST_10[r["job"]] + (t100 - EST_10[r["job"]]) * (x - 0.1) / 0.9
    return t * (W1_FACTOR if r["workers"] == 1 else 1) + OVERHEAD_S


def match(r, filters):
    if not filters:
        return True
    for f in filters:
        p = f.split(":")
        if p[0] != r["level"]:
            continue
        if len(p) > 1 and p[1] != f"w{r['workers']}":
            continue
        if len(p) > 2 and p[2] != r["job"]:
            continue
        if len(p) > 3 and p[3] != f"r{r['rep']}":
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Lenh he thong
# ---------------------------------------------------------------------------
def sh(cmd, check=True, timeout=600):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} -> {p.returncode}: {p.stderr.strip()[-500:]}")
    return p.stdout


def get_json(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)


def hdfs(*args, check=True):
    return sh(["docker", "exec", "namenode", "hdfs", "dfs", *args], check=check)


def running(container):
    return sh(["docker", "inspect", "-f", "{{.State.Running}}", container]).strip() == "true"


def ensure_workers(n):
    """1 worker: dung spark-worker-2 ; 2 worker: bat lai. Cho master bao dung so worker con song."""
    if n == 2 and not running(WORKER2):
        print("[09] bat spark-worker-2", flush=True)
        sh(["docker", "start", WORKER2])
    elif n == 1 and running(WORKER2):
        print("[09] dung spark-worker-2", flush=True)
        sh(["docker", "stop", WORKER2])
    t0 = time.time()
    while True:
        m = get_json(MASTER_JSON)
        if m["aliveworkers"] == n and m["cores"] == 2 * n:
            return
        if time.time() - t0 > 240:
            raise RuntimeError(f"master bao {m['aliveworkers']} worker, can {n}")
        time.sleep(3)


def ensure_idle():
    """Khong co ung dung nao dang giu executor (vd notebook chua tat kernel)."""
    t0 = time.time()
    while True:
        apps = get_json(MASTER_JSON).get("activeapps", [])
        if not apps:
            return
        if time.time() - t0 > 600:
            raise RuntimeError(f"cum dang ban: {[a['name'] for a in apps]}")
        print(f"[09] cho ung dung khac ket thuc: {[a['name'] for a in apps]}", flush=True)
        time.sleep(15)


def prepare_root(level):
    """Goc /perf/<muc>: chep curated/ va features/ tu /data (bang nho, chi lam 1 lan)."""
    root = f"/perf/{level}"
    if subprocess.run(["docker", "exec", "namenode", "hdfs", "dfs", "-test", "-d", f"{root}/features"]).returncode == 0:
        return
    print(f"[09] chuan bi {root}", flush=True)
    hdfs("-mkdir", "-p", root)
    hdfs("-D", "dfs.replication=2", "-cp", "/data/curated", "/data/features", f"{root}/")


# ---------------------------------------------------------------------------
# docker stats trong luc chay
# ---------------------------------------------------------------------------
UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1e3 / 2**20, "MB": 1e6 / 2**20, "GB": 1e9 / 2**20}


def to_mib(s):
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", s.strip())
    return float(m.group(1)) * UNITS.get(m.group(2), 1) if m else None


class StatsSampler(threading.Thread):
    def __init__(self, every=10):
        super().__init__(daemon=True)
        self.every, self.stop_ev, self.peak, self.n = every, threading.Event(), {}, 0

    def run(self):
        while not self.stop_ev.is_set():
            try:
                out = sh(["docker", "stats", "--no-stream", "--format", "{{json .}}", *STATS_CONTAINERS],
                         check=False, timeout=60)
                for line in out.splitlines():
                    d = json.loads(line)
                    name = d.get("Name")
                    mem = to_mib(d.get("MemUsage", "").split("/")[0])
                    cpu = float(d.get("CPUPerc", "0%").rstrip("%") or 0)
                    p = self.peak.setdefault(name, {"mem_mib": 0.0, "cpu_pct": 0.0})
                    p["mem_mib"] = round(max(p["mem_mib"], mem or 0), 1)
                    p["cpu_pct"] = round(max(p["cpu_pct"], cpu), 1)
                self.n += 1
            except Exception as e:  # noqa: BLE001
                print("[09] docker stats loi:", e, flush=True)
            self.stop_ev.wait(self.every)


# ---------------------------------------------------------------------------
# History Server
# ---------------------------------------------------------------------------
def find_app(name, after_ms, timeout=300, allow_incomplete=False):
    """Ung dung co ten 'name', bat dau sau after_ms, da ket thuc (History Server cap nhat sau vai giay)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            for a in get_json(f"{HS}/applications?limit=200"):
                att = a["attempts"][-1]
                if a["name"] == name and att["startTimeEpoch"] >= after_ms - 5000 and (att["completed"] or allow_incomplete):
                    return a["id"], att
        except Exception as e:  # noqa: BLE001
            print("[09] History Server loi:", e, flush=True)
        time.sleep(5)
    return None, None


STAGE_SUM = {"tasks": "numCompleteTasks", "failed_tasks": "numFailedTasks", "executor_run_ms": "executorRunTime",
             "executor_cpu_ns": "executorCpuTime", "gc_ms": "jvmGcTime", "input_bytes": "inputBytes",
             "output_bytes": "outputBytes", "shuffle_read_bytes": "shuffleReadBytes",
             "shuffle_remote_read_bytes": "shuffleRemoteBytesRead", "shuffle_local_read_bytes": "shuffleLocalBytesRead",
             "shuffle_write_bytes": "shuffleWriteBytes", "spill_memory_bytes": "memoryBytesSpilled",
             "spill_disk_bytes": "diskBytesSpilled", "shuffle_fetch_wait_ms": "shuffleFetchWaitTime"}


def stage_agg(stages):
    s = {k: sum(st.get(f, 0) or 0 for st in stages) for k, f in STAGE_SUM.items()}
    mb = lambda b: round(b / 2**20, 1)  # noqa: E731
    return {"stages": len(stages), "tasks": s["tasks"], "failed_tasks": s["failed_tasks"],
            "executor_run_s": round(s["executor_run_ms"] / 1000, 1),
            "executor_cpu_s": round(s["executor_cpu_ns"] / 1e9, 1),
            "cpu_ratio": round(s["executor_cpu_ns"] / 1e6 / s["executor_run_ms"], 3) if s["executor_run_ms"] else None,
            "gc_s": round(s["gc_ms"] / 1000, 1),
            "input_mb": mb(s["input_bytes"]), "output_mb": mb(s["output_bytes"]),
            "shuffle_read_mb": mb(s["shuffle_read_bytes"]), "shuffle_remote_read_mb": mb(s["shuffle_remote_read_bytes"]),
            "shuffle_local_read_mb": mb(s["shuffle_local_read_bytes"]), "shuffle_write_mb": mb(s["shuffle_write_bytes"]),
            "shuffle_fetch_wait_s": round(s["shuffle_fetch_wait_ms"] / 1000, 1),
            "spill_memory_mb": mb(s["spill_memory_bytes"]), "spill_disk_mb": mb(s["spill_disk_bytes"])}


def app_metrics(app_id):
    base = f"{HS}/applications/{app_id}"
    jobs = sorted(get_json(f"{base}/jobs", 120), key=lambda j: j["jobId"])
    group_of = {}
    for j in jobs:                       # stage thuoc job dau tien chua no (job sau chi bo qua stage da co)
        for sid in j["stageIds"]:
            group_of.setdefault(sid, j.get("jobGroup") or "(ngoài giai đoạn)")
    stages = get_json(f"{base}/stages?status=complete", 300)
    failed = get_json(f"{base}/stages?status=failed", 120)
    by_group = defaultdict(list)
    for st in stages:
        by_group[group_of.get(st["stageId"], "(ngoài giai đoạn)")].append(st)
    execs = []
    for e in get_json(f"{base}/allexecutors", 60):
        execs.append({"id": e["id"], "host": e["hostPort"].split(":")[0], "cores": e["totalCores"],
                      "max_memory_mb": round(e["maxMemory"] / 2**20, 1), "tasks": e["totalTasks"],
                      "failed_tasks": e["failedTasks"], "task_time_s": round(e["totalDuration"] / 1000, 1),
                      "gc_s": round(e["totalGCTime"] / 1000, 1),
                      "shuffle_read_mb": round(e["totalShuffleRead"] / 2**20, 1),
                      "shuffle_write_mb": round(e["totalShuffleWrite"] / 2**20, 1),
                      "remove_reason": e.get("removeReason")})
    return {"jobs": len(jobs), "failed_jobs": sum(j["status"] == "FAILED" for j in jobs),
            "failed_stages": len(failed), **stage_agg(stages),
            "by_group": {g: stage_agg(v) for g, v in by_group.items()}, "executors": execs}


# ---------------------------------------------------------------------------
# Mot lan chay
# ---------------------------------------------------------------------------
def run_one(r, git_rev):
    script, extra, rep_file, _, _ = JOBS[r["job"]]
    key = key_of(r)
    tag = f"{r['level']}|w{r['workers']}|r{r['rep']}"
    app_name = f"{script[:-3]}|{tag}"
    out_rel = f"data/output/perf/{key}"
    args = [a.format(scale=LEVELS[r["level"]]) for a in extra]
    ensure_workers(r["workers"])
    ensure_idle()
    os.makedirs(LOG_DIR, exist_ok=True)
    cmd = ["docker", "exec", "-w", WORK, "-e", f"PYTHONPATH={PYPATH}", "-e", f"VIFOOD_DATA_ROOT=/perf/{r['level']}",
           "-e", f"VIFOOD_OUTPUT_DIR={out_rel}", "-e", f"VIFOOD_RUN_TAG={tag}", "jupyter", "python", f"src/{script}", *args]
    timeout = max(1200, 5 * estimate(r))
    print(f"[09] {datetime.now():%H:%M:%S} chay {key} ({' '.join(args) or 'khong tham so'})", flush=True)
    sampler = StatsSampler()
    sampler.start()
    start_ms, t0 = int(time.time() * 1000), time.time()
    with open(os.path.join(LOG_DIR, f"{key}.log"), "w", encoding="utf-8") as log:
        try:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "exec", "jupyter", "pkill", "-f", f"src/{script}"])
            rc = "timeout"
    wall = round(time.time() - t0, 1)
    sampler.stop_ev.set()
    sampler.join(timeout=70)
    rec = {**r, "key": key, "tag": tag, "args": args, "app_name": app_name, "git": git_rev,
           "started_at": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
           "exit_code": rc, "ok": rc == 0, "wall_s": wall, "docker_stats_peak": sampler.peak,
           "docker_stats_samples": sampler.n}
    app_id, att = find_app(app_name, start_ms)
    if app_id:
        rec["app_id"] = app_id
        rec["duration_s"] = round(att["duration"] / 1000, 1)
        try:
            rec["spark"] = app_metrics(app_id)
        except Exception as e:  # noqa: BLE001
            rec["spark_error"] = str(e)
    rp = os.path.join(PROJECT, out_rel, rep_file)
    if rc == 0 and os.path.exists(rp):
        with open(rp, encoding="utf-8") as fh:
            rep = json.load(fh)
        rec["report"] = {k: rep.get(k) for k in ("timings_s", "total_seconds", "generate_write_seconds", "users",
                                                 "events", "hdfs_mb_events") if k in rep}
    if rc != 0:
        with open(os.path.join(LOG_DIR, f"{key}.log"), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        hits = [ln for ln in lines if re.search(r"OutOfMemory|Killed|ExecutorLost|Error|Exception", ln)]
        rec["error"] = (hits[-5:] or lines[-5:])
    with open(RUNS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[09] {key}: {'OK' if rec['ok'] else 'LOI ' + str(rc)}, History Server {rec.get('duration_s')}s, "
          f"wall {wall}s", flush=True)
    return rec


def load_runs():
    runs = {}
    if os.path.exists(RUNS_FILE):
        with open(RUNS_FILE, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    runs[r["key"]] = r          # lan ghi sau thay lan truoc (--retry-failed)
    return runs


# ---------------------------------------------------------------------------
# Tong hop
# ---------------------------------------------------------------------------
def median_run(rs):
    """Lan chay co thoi gian gan trung vi nhat (lay so lieu stage cua lan nay)."""
    m = statistics.median(r["duration_s"] for r in rs)
    return min(rs, key=lambda r: abs(r["duration_s"] - m))


def hdfs_sizes(level):
    out = {}
    for sub in ("events", "results", "models"):
        try:
            line = hdfs("-du", "-s", f"/perf/{level}/{sub}", check=True).split()
            out[sub] = {"mb": round(int(line[0]) / 2**20, 1), "mb_with_replicas": round(int(line[1]) / 2**20, 1)}
        except Exception:  # noqa: BLE001
            pass
    return out


NOTES = [
    "Dữ liệu hành vi là MÔ PHỎNG (bước 04). Danh mục món là món thật.",
    "1 worker = 1 executor 2 core, 2 GB; 2 worker = 2 executor, tổng 4 core, 4 GB. Đổi từ 2 xuống 1 worker giảm CẢ số core "
    "LẪN bộ nhớ executor, nên speedup là của cụm 2 nút so với 1 nút, không tách riêng ảnh hưởng của core và bộ nhớ.",
    "Mọi container chạy trên cùng một máy (máy ảo Docker): shuffle giữa 2 worker đi qua mạng ảo của Docker, không phải "
    "mạng thật; datanode là container riêng nên cả 1 lẫn 2 worker đều không có data locality.",
    "Mức 10% và 50% là dân số SINH MỚI bằng 04 --scale 0.1 / 0.5 (cùng seed, cùng phân bố), không phải tập con của bản 100%.",
    "06b, 06c, 06e, 06f, 06g chạy với --fixed: fit một lần với tham số đã chọn ở bản thật. 06b chỉ chạy view test; 06c bỏ "
    "so sánh MinHash; 06e chỉ fit k = 3, 8, 11; 06f chỉ view test, bỏ dò trọng số, explore_beyond và thí nghiệm món mới; "
    "06g bỏ lưới tham số.",
    "Thời gian là thời lượng ứng dụng theo Spark History Server (gồm khởi động SparkSession). Job chạy 1 lần thì số đo là "
    "lần duy nhất; 05 và 06b ở 100% chạy 3 lần mỗi cấu hình, lấy trung vị.",
    "speedup_by_scale: speedup = T(1 worker) ÷ T(2 worker) của cả chuỗi 04 → 06f và của 04, 05, 06b ở từng mức; ở 10% và "
    "50% mỗi cấu hình chạy 1 lần.",
    "Không đo 07 (nút thắt là ghi MongoDB).",
]


def backfill(runs):
    """Lan chay thieu so lieu History Server (History Server cap nhat cham hon thoi gian cho): tra lai theo ten."""
    changed = False
    for r in runs.values():
        if r.get("app_id") or r.get("exit_code") not in (0, 1):
            continue
        start_ms = int(datetime.fromisoformat(r["started_at"]).timestamp() * 1000)
        app_id, att = find_app(r["app_name"], start_ms, timeout=10, allow_incomplete=True)
        if app_id:
            r.update({"app_id": app_id, "spark": app_metrics(app_id), "backfilled": True})
            if att["completed"]:
                r["duration_s"] = round(att["duration"] / 1000, 1)
            else:
                # Event log khong duoc dong (con file appstatus) du job da xong: lay moc ket thuc cua job cuoi
                jobs = get_json(f"{HS}/applications/{app_id}/jobs", 120)
                end = max(datetime.strptime(j["completionTime"], "%Y-%m-%dT%H:%M:%S.%f%Z").timestamp()
                          for j in jobs if j.get("completionTime"))
                start = datetime.strptime(att["startTime"], "%Y-%m-%dT%H:%M:%S.%f%Z").timestamp()
                r["duration_s"] = round(end - start, 1)
                r["duration_note"] = "event log không được đóng; thời lượng = kết thúc job cuối − bắt đầu ứng dụng"
            changed = True
            print(f"[09] bo sung so lieu History Server cho {r['key']}: {r['duration_s']}s")
    if changed:
        with open(RUNS_FILE, "w", encoding="utf-8") as fh:
            for r in runs.values():
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def summarize():
    runs = load_runs()
    backfill(runs)
    groups = defaultdict(list)
    for r in runs.values():
        groups[(r["level"], r["workers"], r["job"])].append(r)
    level_data = {}
    for r in runs.values():
        if r["job"] == "04" and r.get("ok") and r.get("report"):
            level_data[r["level"]] = {"users": r["report"].get("users"), "events": r["report"].get("events"),
                                      "hdfs_mb_events": r["report"].get("hdfs_mb_events")}
    rows = []
    for (level, w, job), rs in sorted(groups.items(), key=lambda x: (list(LEVELS).index(x[0][0]), x[0][2], x[0][1])):
        ok = [r for r in rs if r.get("ok") and r.get("duration_s") is not None]
        row = {"job": job, "step": JOBS[job][4], "level": level,
               "level_pct": int(LEVELS[level] * 100) if LEVELS[level] else None, "workers": w,
               "n_runs": len(rs), "n_ok": len(ok),
               "failed": [{"rep": r["rep"], "exit_code": r["exit_code"], "error": r.get("error"),
                           "duration_s": r.get("duration_s")} for r in rs if not r.get("ok")]}
        if ok:
            d = sorted(r["duration_s"] for r in ok)
            mr = median_run(ok)
            row.update({"median_s": round(statistics.median(d), 1), "min_s": d[0], "max_s": d[-1], "runs_s": d,
                        "wall_median_s": round(statistics.median(r["wall_s"] for r in ok), 1),
                        "median_rep": mr["rep"], "app_id": mr.get("app_id")})
            if mr.get("duration_note"):
                row["duration_note"] = mr["duration_note"]
            tim = defaultdict(list)
            for r in ok:
                for k, v in ((r.get("report") or {}).get("timings_s") or {}).items():
                    tim[k].append(v)
            row["timings_s"] = {k: round(statistics.median(v), 1) for k, v in tim.items()}
            sp = mr.get("spark") or {}
            row["spark"] = {k: v for k, v in sp.items() if k not in ("by_group", "executors")}
            row["spark_by_group"] = sp.get("by_group")
            row["executors"] = sp.get("executors")
            row["docker_stats_peak"] = mr.get("docker_stats_peak")
            ev = level_data.get(level, {}).get("events")
            if job in ("04", "05") and ev:
                row["events_per_s"] = round(ev / row["median_s"])
        rows.append(row)

    med = {(r["level"], r["workers"], r["job"]): r.get("median_s") for r in rows}
    speedup = []
    for (level, job) in sorted({(r["level"], r["job"]) for r in rows}, key=lambda x: (list(LEVELS).index(x[0]), x[1])):
        t1, t2 = med.get((level, 1, job)), med.get((level, 2, job))
        if t1 and t2:
            s = t1 / t2
            speedup.append({"level": level, "job": job, "step": JOBS[job][4], "t_1w_s": t1, "t_2w_s": t2,
                            "speedup": round(s, 2), "efficiency": round(s / 2, 2)})
    chain = []
    for level in ("s010", "s050", "s100"):
        for w in (1, 2):
            parts = {j: med.get((level, w, j)) for j in CHAIN}
            have = {j: t for j, t in parts.items() if t}
            if have:
                chain.append({"level": level, "level_pct": int(LEVELS[level] * 100), "workers": w,
                              "total_s": round(sum(have.values()), 1), "complete": len(have) == len(CHAIN),
                              "missing": [j for j in CHAIN if j not in have]})
    for c in chain:
        base = next((x for x in chain if x["level"] == "s010" and x["workers"] == c["workers"] and x["complete"]), None)
        if base and c["complete"]:
            c["ratio_vs_10pct"] = round(c["total_s"] / base["total_s"], 2)
        other = next((x for x in chain if x["level"] == c["level"] and x["workers"] != c["workers"]), None)
        if c["workers"] == 2 and other and other["complete"] and c["complete"]:
            c["speedup"] = round(other["total_s"] / c["total_s"], 2)
    scaling = []
    for job in CHAIN:
        t10 = med.get(("s010", 2, job))
        if t10:
            scaling.append({"job": job, "step": JOBS[job][4], "t_10_s": t10, "t_50_s": med.get(("s050", 2, job)),
                            "t_100_s": med.get(("s100", 2, job)),
                            "ratio_50_10": round(med[("s050", 2, job)] / t10, 2) if med.get(("s050", 2, job)) else None,
                            "ratio_100_10": round(med[("s100", 2, job)] / t10, 2) if med.get(("s100", 2, job)) else None})
    # Speedup theo muc du lieu: ca chuoi va cac job nang (04, 05, 06b), moi muc mot dong
    by_scale = []
    for key in ["chain"] + SCALE_JOBS:
        for level in ("s010", "s050", "s100"):
            if key == "chain":
                t1, t2 = (next((c["total_s"] for c in chain if c["level"] == level and c["workers"] == w
                                and c["complete"]), None) for w in (1, 2))
            else:
                t1, t2 = med.get((level, 1, key)), med.get((level, 2, key))
            if t1 and t2:
                by_scale.append({"key": key, "step": "Chuỗi 04 → 06f" if key == "chain" else JOBS[key][4],
                                 "level": level, "level_pct": int(LEVELS[level] * 100), "t_1w_s": t1, "t_2w_s": t2,
                                 "speedup": round(t1 / t2, 2), "efficiency": round(t1 / t2 / 2, 2)})
    for level in level_data:
        level_data[level]["hdfs"] = hdfs_sizes(level)
    try:
        ncpu, mem = sh(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"]).split()
        host = {"docker_cpus": int(ncpu), "docker_mem_gb": round(int(mem) / 1e9, 1)}
    except Exception:  # noqa: BLE001
        host = {}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cluster": {**host, "worker_cores": 2, "worker_memory": "3g", "executor_memory": "2g",
                    "driver_memory": "2g", "shuffle_partitions_default": 8,
                    "configs": {"1 worker": "1 executor × 2 core, 2 GB", "2 worker": "2 executor × 2 core, 2 GB mỗi executor"}},
        "plan": {"chain": CHAIN, "catalog": CATALOG, "repeats_100pct": {"05": 3, "06b": 3},
                 "levels": {k: v for k, v in LEVELS.items()}},
        "data": level_data,
        "rows": rows, "speedup": speedup, "speedup_by_scale": by_scale, "chain_totals": chain, "scaling_2w": scaling,
        "runs_total": len(runs), "runs_failed": sum(not r.get("ok") for r in runs.values()),
        "notes": NOTES,
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"[09] da ghi {REPORT_FILE}: {len(rows)} dong, {len(speedup)} speedup, {len(runs)} lan chay")
    return report


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true", help="chi in ke hoach va thoi gian du kien")
    ap.add_argument("--only", default="", help="muc[:wN[:job[:rK]]], cach nhau dau phay, vd s010:w2,s100:w1:06b")
    ap.add_argument("--with-06b-quick", action="store_true", help="them 06b --quick o 100%%, 1 va 2 worker, 3 lan")
    ap.add_argument("--retry-failed", action="store_true", help="chay lai cac lan da ghi la loi")
    ap.add_argument("--summarize", action="store_true", help="chi tong hop perf_report.json")
    args = ap.parse_args()
    if args.summarize:
        summarize()
        return
    filters = [f.strip() for f in args.only.split(",") if f.strip()]
    done = load_runs()
    plan = [r for r in build_plan(args.with_06b_quick) if match(r, filters)]
    todo = [r for r in plan if key_of(r) not in done or (args.retry_failed and not done[key_of(r)].get("ok"))]
    if args.plan:
        total, w_prev = 0.0, None
        print(f"{'#':>3}  {'lan chay':<22} {'tham so':<14} {'du kien':>8} {'cong don':>9}")
        for i, r in enumerate(plan, 1):
            st = "da co" if r not in todo else ""
            e = estimate(r) + (SWITCH_S if r["workers"] != w_prev else 0)
            w_prev = r["workers"]
            if not st:
                total += e
            args_s = " ".join(a.format(scale=LEVELS[r["level"]]) for a in JOBS[r["job"]][1])
            print(f"{i:>3}  {key_of(r):<22} {args_s:<14} {e / 60:>6.1f}ph {total / 3600:>7.2f}h  {st}")
        print(f"[09] {len(todo)}/{len(plan)} lan can chay, du kien {total / 3600:.2f} gio (uoc tinh)")
        return
    git_rev = sh(["git", "-C", PROJECT, "rev-parse", "--short", "HEAD"], check=False).strip()
    for level in sorted({r["level"] for r in todo}):
        prepare_root(level)
    try:
        for i, r in enumerate(todo, 1):
            print(f"[09] ({i}/{len(todo)})", end=" ", flush=True)
            run_one(r, git_rev)
    finally:
        ensure_workers(2)                 # tra cum ve trang thai binh thuong
    summarize()


if __name__ == "__main__":
    main()
