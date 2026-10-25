"""
06e_kmeans.py - Phan khuc user bang K-means / Bisecting K-means tren dac trung hanh vi (D12, sua doi i).

Dac trung (06a, view val = lich su train): log so su kien, log so phien, ti le nau/xem, ti le cham/nau,
  ti trong mon chay / hai san / ngot-do uong / nhanh / cay / canh / lau trong luot nau,
  ti trong luot nau theo bua (sang, trua, toi, khuya), ti trong cuoi tuan, entropy nhom mon, diem cham trung binh.
  Chi lay user co >= 1 luot nau. Chuan hoa StandardScaler(withMean, withStd).
Chon k = 2..12 theo Silhouette (ClusteringEvaluator). Bao ARI va NMI so voi persona_main (users_truth, CHI de
  kiem chung) tai k da chon VA tai k = 8 (so persona). ARI khong the dat 1: moi user con persona phu, vung, tuoi.

Dau vao : /data/results/models/user_features_val (06a), /data/events/users_truth
Dau ra  : /data/models/kmeans (k = 8, dung cho dashboard - D13)
          /data/results/models/user_clusters (user_id, cluster_k3, cluster_k8, cluster_k11)
          /data/results/models/cluster_profile (k = 3/8/11, cluster, n_users, trung binh tung dac trung, persona pho bien)
          data/output/model_kmeans_report.json

Chay tren cum:  python src/06e_kmeans.py
Chay thu local: python src/06e_kmeans.py --local
Do hieu nang:   python src/06e_kmeans.py --fixed   (D17: chi fit KMeans k = 3, 8, 11)
"""
import math
import os
import sys

from pyspark.ml.clustering import BisectingKMeans, KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06e_kmeans", __doc__)
T = R.Timer()
report = {"mode": "local" if args.local else "cluster"}
REPORT_KS = [3, 8, 11]     # D13: k = 3 (Silhouette cao nhat), 8 (so persona, DASHBOARD dung), 11 (ARI cao nhat)
DASHBOARD_K = 8
FEATS = ["log_events", "log_sessions", "cook_per_view", "rate_per_cook", "share_chay", "share_haisan", "share_ngot",
         "share_nhanh", "share_cay", "share_canh", "share_lau", "slot_0", "slot_1", "slot_2", "slot_3",
         "share_weekend", "cat_entropy", "avg_rating"]
KS = list(range(2, 13)) if not args.quick else [2, 4, 8]
ALGOS = (("KMeans", KMeans), ("BisectingKMeans", BisectingKMeans))
if args.fixed:
    # D17: chi fit KMeans o 3 gia tri k can luu (cluster_k3/k8/k11), bo do k = 2..12 va BisectingKMeans
    report["fixed"] = True
    KS, ALGOS = REPORT_KS, (("KMeans", KMeans),)

with T("features"):
    uf = R.load(spark, P, "user_features", "val").filter("n_cook >= 1")
    va = VectorAssembler(inputCols=FEATS, outputCol="raw")
    sc = StandardScaler(inputCol="raw", outputCol="features", withMean=True, withStd=True)
    x = va.transform(uf)
    x = sc.fit(x).transform(x).select("user_id", "features", *FEATS).cache()
    truth = spark.read.parquet(f"{P.events}/users_truth").select("user_id", "persona_main")
    report["users"] = x.count()
    report["features"] = FEATS


def external(pred_col_df):
    """ARI va NMI giua cot 'prediction' va persona_main (bang cheo tinh bang Spark, cong thuc tren driver)."""
    ct = pred_col_df.join(truth, "user_id").groupBy("prediction", "persona_main").count().collect()
    n = sum(r["count"] for r in ct)
    a, b = {}, {}
    for r in ct:
        a[r["prediction"]] = a.get(r["prediction"], 0) + r["count"]
        b[r["persona_main"]] = b.get(r["persona_main"], 0) + r["count"]
    c2 = lambda m: m * (m - 1) / 2  # noqa: E731
    sij, sa, sb = sum(c2(r["count"]) for r in ct), sum(c2(v) for v in a.values()), sum(c2(v) for v in b.values())
    exp = sa * sb / c2(n)
    ari = (sij - exp) / (0.5 * (sa + sb) - exp)
    mi = sum(r["count"] / n * math.log(n * r["count"] / (a[r["prediction"]] * b[r["persona_main"]])) for r in ct)
    h = lambda d: -sum(v / n * math.log(v / n) for v in d.values())  # noqa: E731
    nmi = 2 * mi / (h(a) + h(b))
    return round(ari, 4), round(nmi, 4)


with T("search_k"):
    ev = ClusteringEvaluator(featuresCol="features", metricName="silhouette", distanceMeasure="squaredEuclidean")
    res, models = [], {}
    for algo, cls in ALGOS:
        for k in KS:
            m = cls(k=k, seed=R.SEED, featuresCol="features", maxIter=30).fit(x)
            pr = m.transform(x)
            ari, nmi = external(pr.select("user_id", "prediction"))
            res.append({"algo": algo, "k": k, "silhouette": round(ev.evaluate(pr), 4), "ari": ari, "nmi": nmi})
            models[(algo, k)] = m
            print(f"[06] {res[-1]}", flush=True)
    report["search"] = res
    best = max(res, key=lambda r: r["silhouette"])
    report["best_by_silhouette"] = best
    report["at_k8"] = [r for r in res if r["k"] == 8]

with T("save"):
    ks = [k for k in REPORT_KS if ("KMeans", k) in models]
    models[("KMeans", DASHBOARD_K if DASHBOARD_K in ks else best["k"])].write().overwrite().save(f"{P.models}/kmeans")
    cl = x.select("user_id")
    for k in ks:
        cl = cl.join(models[("KMeans", k)].transform(x).select("user_id", F.col("prediction").alias(f"cluster_k{k}")),
                     "user_id")
    R.save(cl, P, "user_clusters")
    cl = R.load(spark, P, "user_clusters")
    j = x.join(cl, "user_id").join(truth, "user_id").cache()
    prof = None
    for k in ks:
        col = f"cluster_k{k}"
        p = (j.groupBy(F.col(col).alias("cluster"))
             .agg(F.count("*").alias("n_users"), *[F.round(F.avg(f), 3).alias(f) for f in FEATS]))
        top_p = (j.groupBy(F.col(col).alias("cluster"), "persona_main").count()
                 .withColumn("r", F.row_number().over(Window.partitionBy("cluster").orderBy(F.desc("count"))))
                 .withColumn("share", F.round(F.col("count") / F.sum("count").over(Window.partitionBy("cluster")), 3))
                 .filter("r = 1").select("cluster", F.col("persona_main").alias("persona_pho_bien_kiem_chung"),
                                         F.col("share").alias("persona_share")))
        p = p.join(top_p, "cluster").withColumn("k", F.lit(k))
        prof = p if prof is None else prof.unionByName(p)
    R.save(prof, P, "cluster_profile", coalesce=1)
    report["dashboard_k"] = DASHBOARD_K
    report["summary_k"] = {str(k): [r for r in res if r["k"] == k] for k in ks}
    report["profile"] = [r.asDict() for r in R.load(spark, P, "cluster_profile").orderBy("k", "cluster").collect()]

report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "kmeans", report)
spark.stop()
