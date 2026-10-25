"""
06g_control.py - Thi nghiem doi chung: ALS tren ratings GOC cua ViFoodRec (D06, D12 cau hoi 7).

Muc dich: bang chung dinh luong cho ly do dung du lieu hanh vi mo phong - neu ratings goc chi la nhieu
ngau nhien thi ALS khong khá hon doan trung binh / doan ngau nhien.
Chia ngau nhien 70/10/20 (seed 2026; ratings goc khong co thoi gian):
  - doan ngau nhien: lay mau tu phan phoi diem cua tap train (bang hash, co seed)
  - trung binh chung, bias (lambda chon tren tap 10%), ALS explicit (rank x regParam chon tren tap 10%)
RMSE/MAE tren phan dong chung cua tap 20% (ALS bo user/mon khong co trong train) + ALS thieu thi bias tren moi dong.
So sanh voi muc cai thien cua ALS explicit tren du lieu mo phong (lay tu model_als_report.json).

Dau vao : /data/curated/ratings_original (buoc 02)
Dau ra  : data/output/model_control_report.json

Chay tren cum:  python src/06g_control.py
Chay thu local: python src/06g_control.py --local
Do hieu nang:   python src/06g_control.py --fixed  (D17: lambda, rank, regParam lay tu data/output/model_control_report.json)
"""
import os
import sys

from pyspark.ml.recommendation import ALS
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06g_control", __doc__)
T = R.Timer()
report = {"mode": "local" if args.local else "cluster"}
if args.fixed:
    report["fixed"] = True


def rmse_mae(df, pred):
    r = df.agg(F.count("*").alias("n"), F.sqrt(F.avg((F.col(pred) - F.col("rating")) ** 2)).alias("rmse"),
               F.avg(F.abs(F.col(pred) - F.col("rating"))).alias("mae")).first()
    return {"n": r["n"], "rmse": round(r["rmse"], 4), "mae": round(r["mae"], 4)}


def bias(train, lam):
    mu = train.agg(F.avg("rating")).first()[0]
    bi = train.groupBy("food_id").agg((F.sum(F.col("rating") - mu) / (lam + F.count("*"))).alias("b_i"))
    bu = (train.join(bi, "food_id").groupBy("user_id")
          .agg((F.sum(F.col("rating") - mu - F.col("b_i")) / (lam + F.count("*"))).alias("b_u")))
    return lambda d: (d.join(bu, "user_id", "left").join(bi, "food_id", "left")
                      .withColumn("pred_bias", F.lit(mu) + F.coalesce("b_u", F.lit(0.0)) + F.coalesce("b_i", F.lit(0.0)))
                      .drop("b_u", "b_i"))


with T("control"):
    try:
        r = spark.read.parquet(f"{P.curated}/ratings_original")
    except Exception:
        if not args.local:
            raise
        r = spark.read.parquet("file://" + os.path.join(P.processed_local, "ratings_v2.parquet"))
    r = r.select(F.col("user_id").cast("int"), F.col("food_id").cast("int"), F.col("rating").cast("double")).dropna()
    tr, va, te = r.randomSplit([0.7, 0.1, 0.2], seed=R.SEED)
    tr, va, te = tr.cache(), va.cache(), te.cache()
    mu = tr.agg(F.avg("rating")).first()[0]
    dist = tr.agg(F.collect_list("rating").alias("all"))
    report["rows"] = {"all": r.count(), "train": tr.count(), "val": va.count(), "test": te.count(),
                      "users": r.select("user_id").distinct().count(), "foods": r.select("food_id").distinct().count()}

    grid = []
    if args.fixed:          # D17: tham so da chon cua ban that, bo luoi
        best = R.prod_report(P, "control")["best"]
        lam, be = best["bias_lambda"], best["als"]
    else:
        lam = min((5, 10, 25), key=lambda L: rmse_mae(bias(tr, L)(va), "pred_bias")["rmse"])
        for rk in (8, 16, 32):
            for reg in (0.1, 0.5, 1.0):
                m = ALS(userCol="user_id", itemCol="food_id", ratingCol="rating", rank=rk, regParam=reg, maxIter=15,
                        seed=R.SEED, coldStartStrategy="drop").fit(tr)
                grid.append({"rank": rk, "regParam": reg, **rmse_mae(m.transform(va), "prediction")})
        be = min(grid, key=lambda g: g["rmse"])
    m = ALS(userCol="user_id", itemCol="food_id", ratingCol="rating", rank=be["rank"], regParam=be["regParam"],
            maxIter=15, seed=R.SEED, coldStartStrategy="nan").fit(tr)
    pr = (bias(tr, lam)(m.transform(te))
          .crossJoin(F.broadcast(dist))
          .withColumn("pred_random", F.element_at("all", (F.pmod(F.xxhash64("user_id", "food_id", F.lit(R.SEED)),
                                                                  F.size("all")) + 1).cast("int")))
          .withColumn("pred_mean", F.lit(mu))
          .withColumn("ok", ~F.isnan("prediction")).drop("all").cache())
    common = pr.filter("ok")
    report["best"] = {"bias_lambda": lam, "als": {"rank": be["rank"], "regParam": be["regParam"]}}
    report["tuning_als"] = grid
    report["test_common_rows"] = {"doan_ngau_nhien": rmse_mae(common, "pred_random"),
                                  "trung_binh": rmse_mae(common, "pred_mean"),
                                  "bias": rmse_mae(common, "pred_bias"),
                                  "als_explicit": rmse_mae(common, "prediction")}
    report["test_all_rows"] = {"trung_binh": rmse_mae(pr, "pred_mean"), "bias": rmse_mae(pr, "pred_bias"),
                               "als_thieu_thi_bias": rmse_mae(pr.withColumn(
                                   "p", F.when(F.col("ok"), F.col("prediction")).otherwise(F.col("pred_bias"))), "p")}
    c = report["test_common_rows"]
    report["als_vs_mean_improvement_pct_goc"] = round(100 * (1 - c["als_explicit"]["rmse"] / c["trung_binh"]["rmse"]), 2)
    try:
        sim = R.prod_report(P, "als")["test"]["rating"]["on_common_rows"]
        report["simulated_for_comparison"] = {
            "trung_binh": sim["trung_binh"], "bias": sim["bias"], "als_explicit": sim["als_explicit"],
            "als_vs_mean_improvement_pct": round(100 * (1 - sim["als_explicit"]["rmse"] / sim["trung_binh"]["rmse"]), 2)}
    except (OSError, KeyError):
        pass
    print(f"[06] control {report['test_common_rows']}", flush=True)

report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "control", report)
spark.stop()
