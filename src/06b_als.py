"""
06b_als.py - Baseline va loc cong tac ALS (explicit + implicit), do tham so tren val, ket qua tren test (D12).

Xep hang (danh gia tren MOI user co nau trong thang danh gia, cung 1 tap user cho moi mo hinh):
  random        : 100 mon chon bang hash(user_id, i) - co seed, chay lai ra cung ket qua
  pop_chung     : mon nau nhieu nhat trong lich su
  pop_gan_day   : mon nau nhieu nhat 2 thang cuoi cua lich su
  pop_vung_tuoi : mon nau nhieu nhat cua nhom (vung, nhom tuoi) cua user
  nau_lai       : mon user da nau nhieu nhat trong lich su, thieu thi bo sung bang pop_chung
  als_implicit  : ALS implicitPrefs, do tin cay log1p(1*view + 3*favorite + 5*cook)
Du doan diem (RMSE/MAE tren dong 'rate' cua thang danh gia):
  trung_binh, bias (mu + b_u + b_i, dieu chuan lambda), als_explicit, als_explicit thieu thi dung bias

Do tham so: tu viet vong lap tren view val (khong dung TrainValidationSplit vi no chia ngau nhien).
  ALS implicit: do lan luot alpha {0,25; 0,5; 1; 5; 20; 40} -> rank {32, 64, 128} (128 chi chon neu hon 64 >= 0,003),
  regParam co dinh 0,1, chon theo NDCG@10 tren mau 10.000 user cua val,
  roi kiem tra do nhay trong so implicit {1/3/5, 1/2/10, chi cook}.
Tham so tot nhat duoc fit lai tren view test (lich su = train + val).

Dau vao : /data/results/models/{implicit,ratings,truth,truth_rate,user_groups,pop}_<v>  (06a)
Dau ra  : /data/results/models/recs_<model>_<v>   (user_id, food_id, rank, score) top 100
              view val : user duoc danh gia ; view test: moi user (de 06f lam goi y cuoi)
          /data/results/models/eval_<model>_<v>   do do cua TUNG user (06f dung de tinh khoang tin cay)
          /data/models/als_implicit, /data/models/als_explicit   (model fit tren view test)
          data/output/model_als_report.json

Chay tren cum:  python src/06b_als.py            (--quick: luoi tham so nho)
Chay thu local: python src/06b_als.py --local
"""
import os
import sys

from pyspark.ml.evaluation import RankingEvaluator
from pyspark.ml.recommendation import ALS
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06b_als", __doc__)
T = R.Timer()
N = 100
report = {"mode": "local" if args.local else "cluster", "quick": args.quick}

if args.quick:
    G_BIAS, G_EXP = [10], [(16, 0.1)]
    G_ALPHA, G_RANK, G_REG, MAXITER = [20], [16], [0.1], 5
else:
    G_BIAS = [5, 10, 25]
    G_EXP = [(r, g) for r in (16, 32, 64) for g in (0.05, 0.1, 0.2)]
    # Luoi mo rong 1 lan (D13): alpha tot nhat lien tiep cham bien duoi ({5,20,40} -> 5, roi {1,...} -> 1),
    # rank tot nhat cham bien tren (64). Giu regParam 0,1 (lan chay truoc: 0,1 > 0,01).
    G_ALPHA, G_RANK, G_REG, MAXITER = [0.25, 0.5, 1, 5, 20, 40], [32, 64, 128], [0.1], 10
RANK_MIN_GAIN = 0.003   # rank 128 chi duoc chon neu hon rank 64 tu 0,003 NDCG@10 tro len (D13)
START = {"alpha": G_ALPHA[len(G_ALPHA) // 2], "rank": G_RANK[0], "regParam": G_REG[-1]}


def explode_recs(df, col="recommendations"):
    """Ket qua recommendForUserSubset -> (user_id, food_id, rank, score)."""
    return (df.select("user_id", F.posexplode(col).alias("pos", "r"))
            .select("user_id", F.col("r.food_id").alias("food_id"), (F.col("pos") + 1).alias("rank"),
                    F.col("r.rating").cast("double").alias("score")))


def rank_metrics(recs, truth, name, v, save_eval=True):
    pu = R.per_user_metrics(recs, truth)
    if save_eval:
        R.save(pu, P, f"eval_{name}", v)
        pu = R.load(spark, P, f"eval_{name}", v)
    return R.summarize(pu), pu


def rmse_mae(df, pred="pred"):
    r = df.agg(F.count("*").alias("n"), F.sqrt(F.avg((F.col(pred) - F.col("rating")) ** 2)).alias("rmse"),
               F.avg(F.abs(F.col(pred) - F.col("rating"))).alias("mae")).first()
    return {"n": r["n"], "rmse": round(r["rmse"], 4), "mae": round(r["mae"], 4)}


def clip(c):
    return F.least(F.greatest(c, F.lit(0.5)), F.lit(5.0))


def bias_model(ratings, lam):
    mu = ratings.agg(F.avg("rating")).first()[0]
    bi = ratings.groupBy("food_id").agg((F.sum(F.col("rating") - mu) / (lam + F.count("*"))).alias("b_i"))
    bu = (ratings.join(bi, "food_id").groupBy("user_id")
          .agg((F.sum(F.col("rating") - mu - F.col("b_i")) / (lam + F.count("*"))).alias("b_u")))
    return mu, bu, bi


def bias_predict(df, mu, bu, bi):
    return (df.join(bu, "user_id", "left").join(bi, "food_id", "left")
            .withColumn("pred_bias", clip(F.lit(mu) + F.coalesce("b_u", F.lit(0.0)) + F.coalesce("b_i", F.lit(0.0))))
            .drop("b_u", "b_i"))


def als_implicit(train, alpha, rank, reg, w=R.DEFAULT_W):
    data = train.select("user_id", "food_id", R.conf_expr(w).alias("conf"))
    return ALS(userCol="user_id", itemCol="food_id", ratingCol="conf", implicitPrefs=True, alpha=float(alpha),
               rank=rank, regParam=reg, maxIter=MAXITER, seed=R.SEED, checkpointInterval=5,
               coldStartStrategy="drop").fit(data)


for v in ("val", "test"):
    report[v] = {}
    truth = R.load(spark, P, "truth", v).cache()
    ug = R.load(spark, P, "user_groups", v)
    # val: chi can user duoc danh gia ; test: moi user (06f lam goi y cuoi cho ca 50.000 user)
    target = truth.select("user_id") if v == "val" else ug.select("user_id")
    target = target.join(ug.select("user_id", "region", "age_group"), "user_id").cache()
    pop = R.load(spark, P, "pop", v).cache()
    implicit = R.load(spark, P, "implicit", v).cache()

    # ------------------------------------------------------------------ baseline xep hang
    with T(f"{v}:baselines"):
        items = R.load(spark, P, "item_pop", v).agg(F.array_sort(F.collect_list("food_id")).alias("all"))
        rnd = (target.crossJoin(F.broadcast(items))
               .select("user_id", F.slice(F.array_distinct(F.expr(
                   f"transform(sequence(1, {N + 60}), i -> element_at(all, "
                   f"int(pmod(xxhash64(user_id, i, {R.SEED}), size(all))) + 1))")), 1, N).alias("l"))
               .select("user_id", F.posexplode("l").alias("pos", "food_id"))
               .select("user_id", "food_id", (F.col("pos") + 1).alias("rank"), (-F.col("pos")).cast("double").alias("score")))
        recs = {"random": rnd}
        for name, kind in (("pop_chung", "chung"), ("pop_gan_day", "2 tháng cuối")):
            recs[name] = (target.select("user_id")
                          .crossJoin(F.broadcast(pop.filter(F.col("kind") == kind).select("food_id", "rank", "cooks")))
                          .select("user_id", "food_id", "rank", F.col("cooks").cast("double").alias("score")))
        recs["pop_vung_tuoi"] = (target.join(F.broadcast(pop.filter("kind = 'vùng-tuổi'")), ["region", "age_group"])
                                 .select("user_id", "food_id", "rank", F.col("cooks").cast("double").alias("score")))
        # nau lai: mon da nau (nhieu lan, gan day truoc) + bo sung pop_chung phia sau
        own = (implicit.filter("n_cook > 0").join(target.select("user_id"), "user_id")
               .select("user_id", "food_id", (F.col("n_cook") * 1e6 + F.unix_timestamp("last_ts") / 1e4).alias("s")))
        fill = (target.select("user_id").crossJoin(F.broadcast(pop.filter("kind = 'chung'").select("food_id", "rank")))
                .select("user_id", "food_id", (-F.col("rank")).cast("double").alias("s")))
        rep = (own.unionByName(fill).groupBy("user_id", "food_id").agg(F.max("s").alias("score")))
        recs["nau_lai"] = R.top_n(rep, N).select("user_id", "food_id", "rank", "score")
        report[v]["ranking"] = {}
        for name, df in recs.items():
            R.save(df, P, f"recs_{name}", v)
            report[v]["ranking"][name], _ = rank_metrics(R.load(spark, P, f"recs_{name}", v), truth, name, v)
            print(f"[06] {v} {name} ndcg@10 = {report[v]['ranking'][name][0]['ndcg@10']}", flush=True)

    # ------------------------------------------------------------------ du doan diem
    with T(f"{v}:rating_models"):
        ratings = R.load(spark, P, "ratings", v).cache()
        trate = R.load(spark, P, "truth_rate", v).cache()
        if v == "val":
            tune_b, tune_e = [], []
            for lam in G_BIAS:
                mu, bu, bi = bias_model(ratings, lam)
                tune_b.append({"lambda": lam, **rmse_mae(bias_predict(trate, mu, bu, bi), "pred_bias")})
            best_lam = min(tune_b, key=lambda r: r["rmse"])["lambda"]
            for rk, reg in G_EXP:
                m = ALS(userCol="user_id", itemCol="food_id", ratingCol="rating", rank=rk, regParam=reg,
                        maxIter=15, seed=R.SEED, checkpointInterval=5, coldStartStrategy="drop").fit(ratings)
                tune_e.append({"rank": rk, "regParam": reg,
                               **rmse_mae(m.transform(trate).withColumn("pred", clip(F.col("prediction"))))})
                print(f"[06] val als_explicit rank={rk} reg={reg}: {tune_e[-1]}", flush=True)
            best_e = min(tune_e, key=lambda r: r["rmse"])
            report["tuning_bias"], report["tuning_als_explicit"] = tune_b, tune_e
            report["best_bias_lambda"] = best_lam
            report["best_als_explicit"] = {"rank": best_e["rank"], "regParam": best_e["regParam"]}
        lam = report["best_bias_lambda"]
        be = report["best_als_explicit"]
        mu, bu, bi = bias_model(ratings, lam)
        m_exp = ALS(userCol="user_id", itemCol="food_id", ratingCol="rating", rank=be["rank"], regParam=be["regParam"],
                    maxIter=15, seed=R.SEED, checkpointInterval=5, coldStartStrategy="nan").fit(ratings)
        if v == "test":
            m_exp.write().overwrite().save(f"{P.models}/als_explicit")
        pr = (bias_predict(m_exp.transform(trate), mu, bu, bi)
              .withColumn("pred_als", clip(F.col("prediction")))
              .withColumn("pred_mean", F.lit(mu))
              .withColumn("als_ok", ~F.isnan("prediction")).cache())
        common_rows = pr.filter("als_ok")
        n_all = pr.count()
        report[v]["rating"] = {
            "rows_all": n_all, "rows_common": common_rows.count(),
            "rows_dropped_by_als_pct": round(100 * (1 - common_rows.count() / n_all), 2),
            "on_common_rows": {"trung_binh": rmse_mae(common_rows, "pred_mean"),
                               "bias": rmse_mae(common_rows, "pred_bias"),
                               "als_explicit": rmse_mae(common_rows, "pred_als")},
            "on_all_rows": {"trung_binh": rmse_mae(pr, "pred_mean"), "bias": rmse_mae(pr, "pred_bias"),
                            "als_explicit_thieu_thi_bias": rmse_mae(
                                pr.withColumn("p", F.when(F.col("als_ok"), F.col("pred_als")).otherwise(F.col("pred_bias"))), "p")},
        }
        print(f"[06] {v} rating: {report[v]['rating']['on_common_rows']}", flush=True)
        pr.unpersist(); ratings.unpersist(); trate.unpersist()

    # ------------------------------------------------------------------ ALS implicit
    with T(f"{v}:als_implicit"):
        if v == "val":
            tune_truth = truth.filter("tune")
            tune_users = tune_truth.select("user_id")
            tuning, cache = [], {}

            def try_params(alpha, rank, regParam, w=R.DEFAULT_W):
                key = (alpha, rank, regParam, w)
                if key not in cache:
                    m = als_implicit(implicit, alpha, rank, regParam, w)
                    rc = explode_recs(m.recommendForUserSubset(tune_users, N))
                    s, _ = rank_metrics(rc, tune_truth, "tmp", v, save_eval=False)
                    cache[key] = {"alpha": alpha, "rank": rank, "regParam": regParam, "weights": w,
                                  "ndcg@10": s[0]["ndcg@10"], "p@10": s[0]["p@10"], "r@10": s[0]["r@10"]}
                    tuning.append(cache[key])
                    print(f"[06] val als_implicit {cache[key]}", flush=True)
                return cache[key]["ndcg@10"]

            best = dict(START)
            for name, grid in (("alpha", G_ALPHA), ("rank", G_RANK), ("regParam", G_REG)):
                scores = {x: try_params(**{**best, name: x}) for x in grid}
                best[name] = max(scores, key=scores.get)
                if name == "rank" and best["rank"] == 128 and 64 in scores                         and scores[128] - scores[64] < RANK_MIN_GAIN:
                    best["rank"] = 64
                    report["rank_rule"] = (f"rank 128 ({scores[128]}) hơn rank 64 ({scores[64]}) dưới "
                                           f"{RANK_MIN_GAIN} -> giữ rank 64")
            sens = {w: try_params(**best, w=w) for w in R.IMPLICIT_W}
            report["tuning_als_implicit"] = tuning
            report["best_als_implicit"] = best
            report["sensitivity_implicit_weights_ndcg@10"] = sens
        b = report["best_als_implicit"]
        m_imp = als_implicit(implicit, b["alpha"], b["rank"], b["regParam"])
        if v == "test":
            m_imp.write().overwrite().save(f"{P.models}/als_implicit")
        rc = explode_recs(m_imp.recommendForUserSubset(target.select("user_id"), N))
        R.save(rc, P, "recs_als_implicit", v)
        report[v]["ranking"]["als_implicit"], pu = rank_metrics(R.load(spark, P, "recs_als_implicit", v),
                                                                truth, "als_implicit", v)
        print(f"[06] {v} als_implicit ndcg@10 = {report[v]['ranking']['als_implicit'][0]['ndcg@10']}", flush=True)

    # Kiem tra: do do tu viet (ham mang Spark SQL) khop voi RankingEvaluator cua Spark
    if v == "test":
        with T("check_ranking_evaluator"):
            pred = (R.load(spark, P, "recs_als_implicit", v).filter("rank <= 10").groupBy("user_id")
                    .agg(F.sort_array(F.collect_list(F.struct("rank", "food_id"))).alias("p"))
                    .select("user_id", F.expr("transform(p, x -> CAST(x.food_id AS DOUBLE))").alias("prediction")))
            ev_df = (truth.join(pred, "user_id", "left")
                     .select(F.coalesce("prediction", F.expr("CAST(array() AS array<double>)")).alias("prediction"),
                             F.expr("transform(items, x -> CAST(x AS DOUBLE))").alias("label")))
            chk = {}
            for metric, ours in (("ndcgAtK", "ndcg@10"), ("precisionAtK", "p@10"),
                                 ("meanAveragePrecisionAtK", "ap@10"), ("recallAtK", "r@10")):
                spark_v = RankingEvaluator(metricName=metric, k=10, predictionCol="prediction",
                                           labelCol="label").evaluate(ev_df)
                chk[metric] = {"spark": round(spark_v, 4), "tu_viet": report[v]["ranking"]["als_implicit"][0][ours]}
            report["check_ranking_evaluator"] = chk
            print(f"[06] check RankingEvaluator: {chk}", flush=True)

        with T("ci_test"):
            ev_als = R.load(spark, P, "eval_als_implicit", v)
            report["ci95_test_ndcg@10"] = [
                R.paired_ci(ev_als, R.load(spark, P, f"eval_{o}", v), name_a="als_implicit", name_b=o)
                for o in ("pop_chung", "pop_gan_day", "pop_vung_tuoi", "nau_lai")]
    truth.unpersist(); target.unpersist(); pop.unpersist(); implicit.unpersist()

report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "als", report)
spark.stop()
