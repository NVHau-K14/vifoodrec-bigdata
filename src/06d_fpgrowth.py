"""
06d_fpgrowth.py - Luat ket hop bang FP-Growth (D12, sua doi h).

(1) Nguyen lieu: moi mon la 1 giao dich (array_distinct ingredient_list). Chay 2 lan: giu va bo gia vi.
    FPGrowth(minSupport=0,01, minConfidence=0,3) -> luat + canh (A -> B, lift) cho do thi mang nguyen lieu.
(2) Mam com: moi phien nau co >= 2 mon trong lich su cua view test (2025-10..2026-08) la 1 giao dich.
    FPGrowth(minSupport=0,0002, minConfidence=0,1) -> bang mon an kem (companion).
    Danh gia tren cac phien mam com cua thang 2026-09: voi moi (phien, mon a), du doan 3 mon di kem a;
    trung neu mot mon khac trong phien nam trong 3 mon do (hit rate@3). So voi 2 moc:
      - 3 mon canh/sup pho bien nhat
      - mon hay nau cung nhat theo NHOM MON cua a (dem dong xuat hien trong lich su)

Dau vao : /data/curated/foods, /data/features/dish_features, /data/events/events
Dau ra  : /data/results/models/rules_ingredients (variant, antecedent, consequent, confidence, lift, support)
          /data/results/models/ingredient_edges  (variant, src, dst, confidence, lift, support)  canh 1 -> 1
          /data/results/models/rules_meal, /data/results/models/companion (food_id, companion_id, rank, confidence, lift)
          data/output/model_fpgrowth_report.json

Chay tren cum:  python src/06d_fpgrowth.py
Chay thu local: python src/06d_fpgrowth.py --local
"""
import os
import sys

from pyspark.ml.fpm import FPGrowth
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06d_fpgrowth", __doc__)
T = R.Timer()
report = {"mode": "local" if args.local else "cluster"}
ING_SUP, ING_CONF, MEAL_SUP, MEAL_CONF = 0.01, 0.3, 0.0002, 0.1


def read_or_local(path, local_file):
    try:
        return spark.read.parquet(path)
    except Exception:
        if not args.local:
            raise
        return spark.read.parquet("file://" + os.path.join(P.processed_local, local_file))


dish = read_or_local(f"{P.features}/dish_features", "dish_features.parquet").select("food_id", "dish_name", "dish_category")
names = F.broadcast(dish.select("food_id", "dish_name"))

# ===========================================================================
# 1. LUAT NGUYEN LIEU
# ===========================================================================
with T("ingredients"):
    foods = read_or_local(f"{P.curated}/foods", "foods_v2.parquet")
    base = foods.select("food_id", F.array_distinct(F.expr(
        "filter(transform(ingredient_list, x -> lower(trim(x))), x -> length(x) > 0)")).alias("items"))
    seas = F.array(*[F.lit(s) for s in R.SEASONINGS])
    report["ingredients"] = {}
    all_rules, all_edges = None, None
    for variant, tx in (("giữ gia vị", base), ("bỏ gia vị", base.withColumn("items", F.array_except("items", seas)))):
        tx = tx.filter(F.size("items") > 0).cache()
        m = FPGrowth(itemsCol="items", minSupport=ING_SUP, minConfidence=ING_CONF).fit(tx)
        rules = m.associationRules.withColumn("variant", F.lit(variant)).cache()
        edges = (rules.filter((F.size("antecedent") == 1) & (F.size("consequent") == 1))
                 .select("variant", F.col("antecedent")[0].alias("src"), F.col("consequent")[0].alias("dst"),
                         "confidence", "lift", "support"))
        all_rules = rules if all_rules is None else all_rules.unionByName(rules)
        all_edges = edges if all_edges is None else all_edges.unionByName(edges)
        top = rules.orderBy(F.desc("lift"), F.desc("support")).limit(10).collect()
        report["ingredients"][variant] = {
            "transactions": tx.count(), "items_per_tx_avg": round(tx.select(F.avg(F.size("items"))).first()[0], 2),
            "freq_itemsets": m.freqItemsets.count(), "rules": rules.count(), "edges_1to1": edges.count(),
            "top10_by_lift": [f"{' + '.join(r['antecedent'])} -> {' + '.join(r['consequent'])} "
                              f"(conf {r['confidence']:.2f}, lift {r['lift']:.2f}, sup {r['support']:.3f})" for r in top]}
    R.save(all_rules.select("variant", "antecedent", "consequent", "confidence", "lift", "support"), P,
           "rules_ingredients", coalesce=1)
    R.save(all_edges, P, "ingredient_edges", coalesce=1)

# ===========================================================================
# 2. LUAT MAM COM (lich su view test) + DANH GIA TREN THANG TEST
# ===========================================================================
with T("meal_rules"):
    cfg = R.VIEWS["test"]
    cooks = (spark.read.parquet(f"{P.events}/events").filter("event_type = 'cook'")
             .select("session_id", "food_id", "month"))
    hist_tx = (cooks.filter(F.col("month") <= cfg["hist_max"]).groupBy("session_id")
               .agg(F.array_distinct(F.collect_list("food_id")).alias("items")).filter(F.size("items") >= 2).cache())
    m = FPGrowth(itemsCol="items", minSupport=MEAL_SUP, minConfidence=MEAL_CONF).fit(hist_tx)
    rules = m.associationRules.cache()
    R.save(rules, P, "rules_meal", coalesce=1)
    comp = R.top_n(rules.filter((F.size("antecedent") == 1) & (F.size("consequent") == 1))
                   .select(F.col("antecedent")[0].alias("user_id"), F.col("consequent")[0].alias("food_id"),
                           (F.col("confidence") * 1e3 + F.col("lift") / 1e3).alias("score"), "confidence", "lift"), 5)
    comp = comp.select(F.col("user_id").alias("food_id"), F.col("food_id").alias("companion_id"), "rank",
                       "confidence", "lift")
    R.save(comp, P, "companion", coalesce=1)
    comp = R.load(spark, P, "companion").cache()
    top_rules = (rules.filter((F.size("antecedent") == 1) & (F.size("consequent") == 1))
                 .orderBy(F.desc("lift")).limit(10)
                 .select(F.col("antecedent")[0].alias("a"), F.col("consequent")[0].alias("b"), "confidence", "lift")
                 .join(names.withColumnRenamed("food_id", "a").withColumnRenamed("dish_name", "na"), "a")
                 .join(names.withColumnRenamed("food_id", "b").withColumnRenamed("dish_name", "nb"), "b")
                 .orderBy(F.desc("lift")).collect())
    report["meal"] = {
        "transactions": hist_tx.count(), "items_per_tx_avg": round(hist_tx.select(F.avg(F.size("items"))).first()[0], 2),
        "freq_itemsets": m.freqItemsets.count(), "rules": rules.count(),
        "dishes_with_companion": comp.select("food_id").distinct().count(),
        "top10_by_lift": [f"{r['na']} -> {r['nb']} (conf {r['confidence']:.2f}, lift {r['lift']:.1f})" for r in top_rules]}

with T("meal_eval"):
    test_tx = (cooks.filter(F.col("month") == cfg["eval"]).groupBy("session_id")
               .agg(F.array_distinct(F.collect_list("food_id")).alias("items")).filter(F.size("items") >= 2))
    # moi (phien, mon a): cac mon con lai cua phien la dap an
    qa = (test_tx.select("session_id", "items", F.explode("items").alias("a"))
          .withColumn("others", F.array_remove("items", F.col("a"))).select("session_id", "a", "others").cache())
    n_q = qa.count()
    hc = cooks.filter(F.col("month") <= cfg["hist_max"])
    # Moc 1: 3 canh pho bien nhat
    canh = (hc.join(dish.filter("dish_category = 'canh/súp'").select("food_id"), "food_id").groupBy("food_id").count()
            .orderBy(F.desc("count"), "food_id").limit(4).agg(F.collect_list("food_id").alias("top")))
    # Moc 2: mon hay nau cung nhat theo nhom mon cua a (dong xuat hien trong phien mam com cua lich su)
    pairs = (hist_tx.select("session_id", F.explode("items").alias("a"), "items")
             .select("a", F.explode("items").alias("b")).filter(F.col("a") != F.col("b"))
             .join(dish.select(F.col("food_id").alias("a"), F.col("dish_category").alias("cat")), "a")
             .groupBy("cat", "b").count())
    cat_top = R.top_n(pairs.select(F.col("cat").alias("user_id"), F.col("b").alias("food_id"),
                                   F.col("count").cast("double").alias("score")), 4)
    cat_top = cat_top.groupBy(F.col("user_id").alias("cat")).agg(
        F.expr("transform(sort_array(collect_list(struct(rank, food_id))), x -> x.food_id)").alias("top"))
    rule_top = comp.groupBy("food_id").agg(
        F.expr("transform(sort_array(collect_list(struct(rank, companion_id))), x -> x.companion_id)").alias("top"))
    q = (qa.join(dish.select(F.col("food_id").alias("a"), F.col("dish_category").alias("cat")), "a")
         .crossJoin(F.broadcast(canh.select(F.col("top").alias("t_canh"))))
         .join(F.broadcast(cat_top.withColumnRenamed("top", "t_cat")), "cat", "left")
         .join(F.broadcast(rule_top.select(F.col("food_id").alias("a"), F.col("top").alias("t_rule"))), "a", "left"))

    def top3(col):   # bo chinh mon a, lay 3 mon dau
        return F.slice(F.array_remove(F.coalesce(F.col(col), F.expr("CAST(array() AS array<int>)")), F.col("a")), 1, 3)

    q = (q.withColumn("p_canh", top3("t_canh")).withColumn("p_cat", top3("t_cat")).withColumn("p_rule", top3("t_rule"))
         .withColumn("p_rule_fb", F.when(F.size("p_rule") > 0, F.col("p_rule")).otherwise(F.col("p_cat"))))
    agg = q.agg(*[F.avg((F.size(F.array_intersect(c, "others")) > 0).cast("int")).alias(c)
                  for c in ("p_canh", "p_cat", "p_rule", "p_rule_fb")],
                F.avg((F.size("p_rule") > 0).cast("int")).alias("rule_coverage"),
                F.sum(F.when(F.size("p_rule") > 0, (F.size(F.array_intersect("p_rule", "others")) > 0).cast("int"))).alias("hit_cov"),
                F.sum((F.size("p_rule") > 0).cast("int")).alias("n_cov")).first()
    report["meal_eval_hit_rate@3"] = {
        "test_sessions": test_tx.count(), "queries (phiên, món)": n_q,
        "moc_3_canh_pho_bien": round(agg["p_canh"], 4),
        "moc_theo_nhom_mon": round(agg["p_cat"], 4),
        "luat_fpgrowth": round(agg["p_rule"], 4),
        "luat_fpgrowth_thieu_thi_theo_nhom_mon": round(agg["p_rule_fb"], 4),
        "luat_do_phu": round(agg["rule_coverage"], 4),
        "luat_tren_phan_co_luat": round(agg["hit_cov"] / agg["n_cov"], 4) if agg["n_cov"] else None}
    print(f"[06] meal eval {report['meal_eval_hit_rate@3']}", flush=True)

report["params"] = {"ingredients": {"minSupport": ING_SUP, "minConfidence": ING_CONF},
                    "meal": {"minSupport": MEAL_SUP, "minConfidence": MEAL_CONF}}
report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "fpgrowth", report)
spark.stop()
