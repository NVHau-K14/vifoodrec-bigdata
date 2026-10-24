"""
06a_split.py - Chia du lieu theo thoi gian cho buoc 06 va tinh moi bang phu thuoc lich su (D12).

Hai "view" (rec_common.VIEWS):
  val : lich su = 2025-10..2026-07, danh gia 2026-08  -> do tham so
  test: lich su = 2025-10..2026-08, danh gia 2026-09  -> ket qua cuoi + goi y cuoi
Moi bang duoi day duoc ghi RIENG cho tung view (hau to _val / _test), tinh chi tu lich su cua view do.

Dau vao : HDFS /data/events/{events,users}, /data/features/dish_features
Dau ra  : HDFS /data/results/models/
            implicit_<v>      (user_id, food_id, n_view, n_favorite, n_cook, n_rate, last_ts)  ma tran implicit
            ratings_<v>       (user_id, food_id, rating)                   dong 'rate' trong lich su
            user_groups_<v>   (user_id, region, age_group, n_events, n_cooks, n_rates, group, is_eval, tune)
            truth_<v>         (user_id, items, group, region, age_group, tune)   mon NAU trong thang danh gia
            truth_rate_<v>    (user_id, food_id, rating)                   dong 'rate' trong thang danh gia
            pop_<v>           (kind, region, age_group, food_id, cooks, rank) top 100 popularity
            item_pop_<v>      (food_id, cooks, share)                      ca 5.499 mon (cho novelty)
            user_features_<v> (user_id, ...)                               dac trung hanh vi (K-means, ngu canh)
          data/output/model_split_report.json

Nhom user (dinh nghia DUY NHAT o day, luat cold-start cua 06f dung lai): so su kien trong lich su
  0 -> lanh, 1-19 -> it, >= 20 -> am.

Chay tren cum:  python src/06a_split.py
Chay thu local: python src/06a_split.py --local
"""
import os
import sys

from pyspark import StorageLevel
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06a_split", __doc__)
T = R.Timer()
report = {"mode": "local" if args.local else "cluster", "warm_min_events": R.WARM_MIN_EVENTS,
          "tune_users": R.TUNE_USERS, "views": {}}

with T("load"):
    ev = (spark.read.parquet(f"{P.events}/events")
          .select("user_id", "food_id", "event_type", "ts", "meal_slot", "session_id", "rating", "month")
          .persist(StorageLevel.MEMORY_AND_DISK))
    users = spark.read.parquet(f"{P.events}/users").select("user_id", "region", "age_group")
    try:
        dish = spark.read.parquet(f"{P.features}/dish_features")
    except Exception:
        if not args.local:
            raise
        dish = spark.read.parquet("file://" + os.path.join(P.processed_local, "dish_features.parquet"))
    dish = F.broadcast(dish.select(
        "food_id", "dish_category", "dish_type_fixed",
        F.col("is_vegetarian").cast("int").alias("f_chay"),
        F.col("main_protein").isin("hải sản", "cá").cast("int").alias("f_haisan"),
        F.col("dish_type_fixed").isin("Món ngọt", "Đồ uống").cast("int").alias("f_ngot"),
        F.col("is_quick").cast("int").alias("f_nhanh"),
        F.col("is_spicy").cast("int").alias("f_cay"),
        (F.col("dish_category") == "canh/súp").cast("int").alias("f_canh"),
        (F.col("dish_category") == "lẩu").cast("int").alias("f_lau")))
    n_events = ev.count()
    n_users_all = users.count()
report["events"] = n_events
report["users"] = n_users_all


def cnt(t, alias):
    return F.sum((F.col("event_type") == t).cast("int")).alias(alias)


SLOTS = ["sáng", "trưa", "tối", "khuya"]
SHARE_COLS = ["f_chay", "f_haisan", "f_ngot", "f_nhanh", "f_cay", "f_canh", "f_lau"]

for v, cfg in R.VIEWS.items():
    rv = {"history": f"2025-10 -> {cfg['hist_max']}", "eval_month": cfg["eval"]}
    with T(f"{v}:history"):
        hist = ev.filter(F.col("month") <= cfg["hist_max"])
        evm = ev.filter(F.col("month") == cfg["eval"])

        implicit = (hist.groupBy("user_id", "food_id")
                    .agg(cnt("view", "n_view"), cnt("favorite", "n_favorite"), cnt("cook", "n_cook"),
                         cnt("rate", "n_rate"), F.max("ts").alias("last_ts")))
        R.save(implicit, P, "implicit", v)
        ratings = hist.filter("event_type = 'rate'").select("user_id", "food_id", F.col("rating").cast("double"))
        R.save(ratings, P, "ratings", v)

        uh = hist.groupBy("user_id").agg(F.count("*").alias("n_events"), cnt("cook", "n_cooks"),
                                         cnt("rate", "n_rates"))
        eval_users = evm.filter("event_type = 'cook'").select("user_id").distinct()
        # Mau do tham so: TUNE_USERS user duoc danh gia dau tien theo hash(user_id) - on dinh khi chay lai
        tune = (eval_users.withColumn("h", F.xxhash64("user_id", F.lit(R.SEED)))
                .withColumn("r", F.row_number().over(Window.orderBy("h", "user_id")))
                .filter(F.col("r") <= R.TUNE_USERS).select("user_id", F.lit(True).alias("tune")))
        ug = (users.join(uh, "user_id", "left").fillna(0, ["n_events", "n_cooks", "n_rates"])
              .withColumn("group", R.group_expr())
              .join(eval_users.withColumn("is_eval", F.lit(True)), "user_id", "left")
              .join(tune, "user_id", "left")
              .fillna(False, ["is_eval", "tune"]))
        R.save(ug, P, "user_groups", v)
        ug = R.load(spark, P, "user_groups", v).cache()

    with T(f"{v}:truth"):
        truth = (evm.filter("event_type = 'cook'").groupBy("user_id")
                 .agg(F.array_sort(F.collect_set("food_id")).alias("items"))
                 .join(ug.select("user_id", "group", "region", "age_group", "tune"), "user_id"))
        R.save(truth, P, "truth", v)
        R.save(evm.filter("event_type = 'rate'").select("user_id", "food_id", F.col("rating").cast("double")),
               P, "truth_rate", v)
        truth = R.load(spark, P, "truth", v)
        rv["eval_users"] = truth.count()
        rv["eval_users_by_group"] = {r["group"]: r["count"] for r in truth.groupBy("group").count().collect()}
        rv["tune_users"] = truth.filter("tune").count()
        rv["truth_items_per_user_avg"] = round(truth.select(F.avg(F.size("items"))).first()[0], 2)
        rv["eval_rate_rows"] = evm.filter("event_type = 'rate'").count()
        rv["history_events"] = hist.count()
        rv["history_users"] = uh.count()
        rv["implicit_pairs"] = R.load(spark, P, "implicit", v).count()
        rv["history_rate_rows"] = R.load(spark, P, "ratings", v).count()
        rv["users_by_group_all"] = {r["group"]: r["count"] for r in ug.groupBy("group").count().collect()}

    with T(f"{v}:popularity"):
        cooks = hist.filter("event_type = 'cook'")
        all_items = dish.select("food_id")
        ipop = (all_items.join(cooks.groupBy("food_id").agg(F.count("*").alias("cooks")), "food_id", "left")
                .fillna(0, ["cooks"]))
        tot = ipop.agg(F.sum("cooks")).first()[0]
        R.save(ipop.withColumn("share", F.col("cooks") / F.lit(tot)), P, "item_pop", v, coalesce=1)

        w_seg = Window.partitionBy("region", "age_group").orderBy(F.desc("cooks"), "food_id")
        w_all = Window.orderBy(F.desc("cooks"), "food_id")
        g = (cooks.groupBy("food_id").agg(F.count("*").alias("cooks"))
             .withColumn("rank", F.row_number().over(w_all)).filter("rank <= 100")
             .select(F.lit("chung").alias("kind"), F.lit(None).cast("string").alias("region"),
                     F.lit(None).cast("string").alias("age_group"), "food_id", "cooks", "rank"))
        rc = (cooks.filter(F.col("month").isin(cfg["recent"])).groupBy("food_id").agg(F.count("*").alias("cooks"))
              .withColumn("rank", F.row_number().over(w_all)).filter("rank <= 100")
              .select(F.lit("2 tháng cuối").alias("kind"), F.lit(None).cast("string").alias("region"),
                      F.lit(None).cast("string").alias("age_group"), "food_id", "cooks", "rank"))
        sg = (cooks.join(F.broadcast(users), "user_id").groupBy("region", "age_group", "food_id")
              .agg(F.count("*").alias("cooks"))
              .withColumn("rank", F.row_number().over(w_seg)).filter("rank <= 100")
              .select(F.lit("vùng-tuổi").alias("kind"), "region", "age_group", "food_id", "cooks", "rank"))
        R.save(g.unionByName(rc).unionByName(sg), P, "pop", v, coalesce=1)
        rv["pop_rows"] = R.load(spark, P, "pop", v).groupBy("kind").count().rdd.collectAsMap()

    with T(f"{v}:user_features"):
        hc = cooks.join(dish, "food_id")
        base = hist.groupBy("user_id").agg(
            F.count("*").alias("n_events"), F.countDistinct("session_id").alias("n_sessions"),
            cnt("view", "n_view"), cnt("cook", "n_cook"), cnt("rate", "n_rate"),
            F.avg("rating").alias("avg_rating"))
        shares = hc.groupBy("user_id").agg(
            *[F.avg(c).alias(c.replace("f_", "share_")) for c in SHARE_COLS],
            *[F.avg((F.col("meal_slot") == s).cast("int")).alias(f"slot_{i}") for i, s in enumerate(SLOTS)],
            F.avg(F.dayofweek("ts").isin(1, 7).cast("int")).alias("share_weekend"))
        cat = hc.groupBy("user_id", "dish_category").count()
        ent = (cat.withColumn("p", F.col("count") / F.sum("count").over(Window.partitionBy("user_id")))
               .groupBy("user_id").agg((-F.sum(F.col("p") * F.log2("p"))).alias("cat_entropy")))
        mu = hist.filter("event_type = 'rate'").agg(F.avg("rating")).first()[0]
        slot_cols = [f"slot_{i}" for i in range(len(SLOTS))]
        feat = (base.join(shares, "user_id", "left").join(ent, "user_id", "left")
                .fillna(0.0, [c.replace("f_", "share_") for c in SHARE_COLS] + slot_cols
                        + ["share_weekend", "cat_entropy"])
                .fillna(mu, ["avg_rating"])
                .withColumn("log_events", F.log1p("n_events"))
                .withColumn("log_sessions", F.log1p("n_sessions"))
                .withColumn("cook_per_view", F.coalesce(F.try_divide("n_cook", "n_view"), F.lit(0.0)))
                .withColumn("rate_per_cook", F.coalesce(F.try_divide("n_rate", "n_cook"), F.lit(0.0)))
                # bua hay nau nhat (khong co luot nau -> null)
                .withColumn("pref_slot", F.when(F.col("n_cook") > 0, F.element_at(
                    F.array(*[F.lit(s) for s in SLOTS]),
                    F.array_position(F.array(*[F.col(c) for c in slot_cols]),
                                     F.greatest(*[F.col(c) for c in slot_cols])).cast("int")))))
        R.save(feat, P, "user_features", v)
        rv["user_features_rows"] = R.load(spark, P, "user_features", v).count()
    report["views"][v] = rv
    ug.unpersist()

# Kiem tra goi y cua chat: so user lanh o test tinh theo train+val, so voi tinh theo train
t_users = R.load(spark, P, "truth", "test").select("user_id")
cold_by_train = t_users.join(R.load(spark, P, "user_groups", "val").filter("group = 'lạnh'"), "user_id").count()
report["check_cold_test_users"] = {"theo train+val (dung)": report["views"]["test"]["eval_users_by_group"].get("lạnh", 0),
                                   "theo train (cach tinh cu)": cold_by_train}
report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "split", report)
print(report)
spark.stop()
