"""
rec_common.py - Ham dung chung cho buoc 06 (goi y mon an). Khong phai mot buoc cua pipeline.

  - VIEWS, group_expr()   : 2 "view" du lieu (D12) va nhom user lanh / it / am
  - setup()               : tham so dong lenh chung, SparkSession, Paths, thu muc checkpoint
  - Timer                 : do thoi gian tung phan (dua vao report, dung cho phan do hieu nang)
  - save() / load()       : ghi / doc bang trung gian /data/results/models/<ten>_<view>
  - conf_expr()           : do tin cay implicit tu so lan xem / luu / nau
  - top_n()               : cat top-N theo diem trong tung user -> (user_id, food_id, rank, score)
  - per_user_metrics()    : P@K, R@K, NDCG@K, AP@K cho TUNG user bang ham mang Spark SQL
  - summarize(), paired_ci(): trung binh theo nhom user, khoang tin cay 95% cua hieu so ghep cap
  - write_report()        : data/output/model_<x>_report.json

View (D12):
  val : lich su = 2025-10..2026-07 (train)       , danh gia thang 2026-08 -> do tham so
  test: lich su = 2025-10..2026-08 (train + val) , danh gia thang 2026-09 -> ket qua cuoi
"""
import argparse
import contextlib
import json
import math
import os
import sys
import time

from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, get_spark  # noqa: E402

VIEWS = {
    "val": {"hist_max": "2026-07", "eval": "2026-08", "recent": ["2026-06", "2026-07"]},
    "test": {"hist_max": "2026-08", "eval": "2026-09", "recent": ["2026-07", "2026-08"]},
}
SEED = 2026
KS = (5, 10)
WARM_MIN_EVENTS = 20        # nhom user theo so su kien trong lich su: 0 lanh, 1-19 it, >=20 am
TUNE_USERS = 10_000         # mau user cua val de do tham so (D12, sua doi f)
IMPLICIT_W = {"1/3/5": (1.0, 3.0, 5.0), "1/2/10": (1.0, 2.0, 10.0), "chỉ cook": (0.0, 0.0, 1.0)}
DEFAULT_W = "1/3/5"
# Gia vi pho bien (giong SEASONINGS cua buoc 05): bo khoi token noi dung (06c) va luat nguyen lieu (06d)
SEASONINGS = ["muối", "dầu ăn", "đường", "đường trắng", "hạt nêm", "tiêu", "tiêu xay", "nước mắm", "bột ngọt",
              "nước tương", "nước", "dầu hào", "dầu mè", "giấm", "gia vị nêm sẵn", "dầu điều", "tương ớt",
              "rượu trắng", "bột năng", "bột bắp", "đường phèn", "ớt bột", "nước cốt chanh",
              "hạt nêm chay knorr nấm hương", "giấm gạo lên men ajinomoto", "bột nở", "vani", "tỏi băm",
              "hành tím băm", "hành tỏi băm", "ớt băm"]


def group_expr(n_events_col="n_events"):
    c = F.col(n_events_col)
    return F.when(c == 0, "lạnh").when(c < WARM_MIN_EVENTS, "ít").otherwise("ấm")


def setup(app, doc=None, extra=None):
    """Tham so chung (--local, --quick) + SparkSession + Paths. extra(ap) de them tham so rieng."""
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--local", action="store_true", help="chay Spark local tren data/hdfs_local (ban 10%%)")
    ap.add_argument("--quick", action="store_true", help="luoi tham so nho de chay thu")
    if extra:
        extra(ap)
    args = ap.parse_args()
    spark = get_spark(app, local=args.local)
    P = Paths(local=args.local)
    spark.sparkContext.setCheckpointDir(P.checkpoint)
    os.makedirs(P.output_local, exist_ok=True)
    return args, spark, P


class Timer:
    def __init__(self):
        self.t0, self.parts = time.time(), {}

    @contextlib.contextmanager
    def __call__(self, name):
        t = time.time()
        yield
        self.parts[name] = round(time.time() - t, 1)
        print(f"[06] {name}: {self.parts[name]}s", flush=True)

    def total(self):
        return round(time.time() - self.t0, 1)


def path(P, name, view=None):
    return f"{P.results}/models/{name}" + (f"_{view}" if view else "")


def save(df, P, name, view=None, coalesce=None):
    p = path(P, name, view)
    (df.coalesce(coalesce) if coalesce else df).write.mode("overwrite").parquet(p)
    return p


def load(spark, P, name, view=None):
    return spark.read.parquet(path(P, name, view))


def conf_expr(w=DEFAULT_W):
    """Do tin cay implicit = log1p(a*view + b*favorite + c*cook) (D12)."""
    a, b, c = IMPLICIT_W[w]
    return F.log1p(a * F.col("n_view") + b * F.col("n_favorite") + c * F.col("n_cook"))


def top_n(df, n, score="score", tie="food_id"):
    """(user_id, food_id, score) -> top-n moi user, them cot rank (1 = tot nhat)."""
    w = Window.partitionBy("user_id").orderBy(F.desc(score), F.col(tie))
    return df.withColumn("rank", F.row_number().over(w)).filter(F.col("rank") <= n)


# ===========================================================================
# DO DO XEP HANG CHO TUNG USER
# ===========================================================================
def per_user_metrics(recs, truth, ks=KS, extra_cols=("group",)):
    """
    recs : (user_id, food_id, rank)   - danh sach goi y (co the thieu user)
    truth: (user_id, items array<int>, <extra_cols>) - MOI user duoc danh gia (D12: cung tap user)
    -> 1 dong / user: so mon dap an, so mon goi y va p@k, r@k, ndcg@k, ap@k.
       User khong co goi y nhan danh sach rong -> moi do do = 0.
    """
    kmax = max(ks)
    pred = (recs.filter(F.col("rank") <= kmax)
            .groupBy("user_id")
            .agg(F.sort_array(F.collect_list(F.struct("rank", "food_id"))).alias("_p"))
            .select("user_id", F.expr("transform(_p, x -> x.food_id)").alias("pred")))
    df = (truth.join(pred, "user_id", "left")
          .withColumn("pred", F.coalesce("pred", F.expr("CAST(array() AS array<int>)")))
          .withColumn("hits", F.expr("transform(pred, x -> IF(array_contains(items, x), 1, 0))")))
    cols = ["user_id", *extra_cols, F.size("items").alias("n_truth"), F.size("pred").alias("n_pred")]
    for k in ks:
        hk = f"slice(hits, 1, {k})"
        nh = f"aggregate({hk}, 0, (a, x) -> a + x)"
        m = f"least({k}, size(items))"
        cols += [
            F.expr(f"{nh} / {k}").alias(f"p@{k}"),
            F.expr(f"{nh} / size(items)").alias(f"r@{k}"),
            F.expr(f"aggregate(transform({hk}, (x, i) -> x / log2(i + 2)), CAST(0 AS DOUBLE), (a, y) -> a + y)"
                   f" / aggregate(transform(sequence(0, {m} - 1), i -> 1 / log2(i + 2)), CAST(0 AS DOUBLE),"
                   f" (a, y) -> a + y)").alias(f"ndcg@{k}"),
            # AP@K: tong precision tai vi tri co hit / min(K, so mon dap an) - giong RankingMetrics cua Spark
            F.expr(f"aggregate(transform({hk}, (x, i) -> x * aggregate(slice({hk}, 1, i + 1), 0, (a, y) -> a + y)"
                   f" / (i + 1)), CAST(0 AS DOUBLE), (a, y) -> a + y) / {m}").alias(f"ap@{k}"),
        ]
    return df.select(*cols)


METRIC_COLS = [f"{m}@{k}" for k in KS for m in ("p", "r", "ndcg", "ap")]


def summarize(per_user, by="group", cols=METRIC_COLS, nd=4):
    """Trung binh do do theo nhom user + dong 'tất cả'. Tra ve list dict (dua vao report)."""
    aggs = [F.count("*").alias("n_users")] + [F.round(F.avg(c), nd).alias(c) for c in cols]
    rows = [r.asDict() for r in per_user.groupBy(by).agg(*aggs).collect()]
    rows.append({by: "tất cả", **per_user.agg(*aggs).first().asDict()})
    order = {"tất cả": 0, "ấm": 1, "ít": 2, "lạnh": 3}
    return sorted(rows, key=lambda r: order.get(r[by], 9))


def paired_ci(a, b, col="ndcg@10", name_a="a", name_b="b", where=None):
    """Hieu so ghep cap theo user (a - b) va khoang tin cay 95% (xap xi chuan, n lon)."""
    d = a.select("user_id", F.col(col).alias("x")).join(b.select("user_id", F.col(col).alias("y")), "user_id")
    if where is not None:
        d = d.join(where, "user_id")
    r = d.agg(F.count("*").alias("n"), F.avg("x").alias("ma"), F.avg("y").alias("mb"),
              F.avg(F.col("x") - F.col("y")).alias("diff"), F.stddev(F.col("x") - F.col("y")).alias("sd")).first()
    half = 1.96 * (r["sd"] or 0) / math.sqrt(r["n"]) if r["n"] else None
    return {"so_sanh": f"{name_a} - {name_b}", "metric": col, "n_users": r["n"],
            name_a: round(r["ma"], 4), name_b: round(r["mb"], 4), "hieu": round(r["diff"], 4),
            "ci95": [round(r["diff"] - half, 4), round(r["diff"] + half, 4)] if half is not None else None}


def write_report(P, name, report):
    with open(os.path.join(P.output_local, f"model_{name}_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
