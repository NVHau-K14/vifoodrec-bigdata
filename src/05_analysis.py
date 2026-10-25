"""
05_analysis.py - Phan tich hanh vi an uong bang Spark SQL + DataFrame.

Luu y: hanh vi la du lieu MO PHONG (buoc 04). Ket qua cho thay pipeline tim lai duoc cac quy luat
da cai vao bo sinh, khong phai phat hien ve nguoi dung that. Khong phan tich calo / cooking_time (so ngau nhien).

Dau vao : HDFS /data/events/events      su kien (Parquet, chia theo thang)  - ket qua 04
          HDFS /data/events/users       vung mien, nhom tuoi
          HDFS /data/features/dish_features   dac trung mon - ket qua 03
          HDFS /data/curated/foods      ingredient_list, image_link - ket qua 02
Dau ra  : HDFS /data/results/analysis/<bang>/   (Parquet, moi bang 1 thu muc)
          data/output/analysis/<bang>.json       (ban nho cho dashboard / buoc 07)
          data/output/analysis/explain.txt       (ke hoach thuc thi cua 2 truy van, dua vao bao cao)
          data/output/analysis_report.json       (so lieu chinh + thoi gian tung phan)

Cac bang:
  Thoi gian   heatmap_hour_dow, trend_month_category, season_month, top_dish_by_slot
  Nhom        lift_by_group      (bua, ngay thuong/cuoi tuan, vung, tuoi) x (nhom mon, dam, cach nau, cay, nhanh...)
  Pheu        funnel_by_category (dem theo su kien va theo cap user-mon), funnel_users trong report
  Mon         dish_stats, catalog_vs_cooked, top_ingredients
  Hanh vi     rating_dist, session_size, repeat_by_category, user_activity, long_tail_curve

Cach xu ly:
  - Doc events 1 lan (chi lay cot can dung), join broadcast voi users (50k dong), persist MEMORY_AND_DISK.
  - "Tong hop truoc, join sau": gom su kien theo food_id thanh 2 khoi nho (cube_cook, monthly)
    roi moi join dac trung mon (5.499 dong, broadcast) -> join tren vai tram nghin dong thay vi 23 trieu.
  - Mot phan viet bang Spark SQL (heatmap, top mon theo bua, pheu dung ROLLUP), phan con lai bang DataFrame.

Chay tren cum:  python src/05_analysis.py            (trong terminal Jupyter)
Chay thu local: python src/05_analysis.py --local    (doc data/hdfs_local, vd ban 10% cua 04)
"""
import argparse
import contextlib
import io
import json
import os
import sys
import time
from functools import reduce

from pyspark import StorageLevel
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, Timer, get_spark  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--local", action="store_true", help="chay Spark local (khong can cum)")
args = ap.parse_args()

spark = get_spark("05_analysis", local=args.local)
P = Paths(local=args.local)
OUT = f"{P.results}/analysis"
OUT_LOCAL = os.path.join(P.output_local, "analysis")
os.makedirs(OUT_LOCAL, exist_ok=True)

t0 = time.time()
tables, report = {}, {}
# Do thoi gian tung phan + job group Spark cung ten (phan hieu nang cua bao cao, D17)
step = Timer("05")
timings = step.parts


def read_parquet(path, local_fallback):
    """Khi local ma chua chay 02/03 o che do local thi doc ban xuat ra data/processed."""
    try:
        return spark.read.parquet(path)
    except Exception:
        if not args.local:
            raise
        return spark.read.parquet("file://" + os.path.join(P.processed_local, local_fallback))


def save(df, name, order=None, json_limit=None, to_json=True):
    """Ghi 1 bang ket qua len HDFS (1 file) + JSON nho tren may. Tra ve cac dong da collect."""
    if order:
        df = df.orderBy(*order)
    res = df.coalesce(1).persist()
    res.write.mode("overwrite").parquet(f"{OUT}/{name}")
    rows = res.collect()
    res.unpersist()
    tables[name] = len(rows)
    if to_json:
        recs = [r.asDict() for r in (rows[:json_limit] if json_limit else rows)]
        with open(os.path.join(OUT_LOCAL, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1, default=str)
    return rows


def pct(num, den, nd=2):
    return F.round(100 * num / den, nd)


def cnt(t, alias):
    """Dem so su kien loai t trong 1 lan groupBy (thay vi loc 4 lan)."""
    return F.sum((F.col("event_type") == t).cast("int")).alias(alias)


# ===========================================================================
# 1. DOC DU LIEU, BANG CO SO (persist) VA 2 KHOI TONG HOP
# ===========================================================================
DISH_COLS = ["food_id", "dish_name", "dish_category", "dish_type_fixed", "main_protein", "main_method",
             "is_spicy", "is_quick", "is_vegetarian", "season"]
DOW_VN = F.array(*[F.lit(x) for x in ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]])   # dayofweek: 1 = CN

with step("load_cache"):
    dish = read_parquet(f"{P.features}/dish_features", "dish_features.parquet").select(*DISH_COLS).cache()
    foods = (read_parquet(f"{P.curated}/foods", "foods_v2.parquet")
             .select("food_id", "image_link", "ingredient_list"))
    users = spark.read.parquet(f"{P.events}/users").select("user_id", "region", "age_group")
    ev_raw = spark.read.parquet(f"{P.events}/events")

    base = (ev_raw.select("user_id", "food_id", "event_type", "meal_slot", "session_id", "rating", "month",
                          F.hour("ts").alias("hour"), F.dayofweek("ts").alias("dow"))
            .withColumn("day_type", F.when(F.col("dow").isin(1, 7), "cuối tuần").otherwise("ngày thường"))
            .join(F.broadcast(users), "user_id")
            .persist(StorageLevel.MEMORY_AND_DISK))
    n_events = base.count()
    n_dish = dish.count()
    base.createOrReplaceTempView("ev")
    dish.createOrReplaceTempView("dish")
    foods.select("food_id", "image_link").createOrReplaceTempView("food_img")

with step("cubes"):
    # Khoi 1: luot nau theo (bua, loai ngay, vung, tuoi, mon) -> toi da 4*2*3*4*5.499 dong
    cube_cook = (base.filter("event_type = 'cook'")
                 .groupBy("meal_slot", "day_type", "region", "age_group", "food_id")
                 .agg(F.count("*").alias("cooks"))
                 .join(F.broadcast(dish), "food_id")
                 .persist())
    # Khoi 2: 4 loai su kien theo (thang, vung, mon)
    monthly = (base.groupBy("month", "region", "food_id")
               .agg(cnt("view", "views"), cnt("favorite", "favorites"), cnt("cook", "cooks"),
                    cnt("rate", "rates"), F.sum("rating").alias("rating_sum"))
               .join(F.broadcast(dish), "food_id")
               .persist())
    cube_cook.createOrReplaceTempView("cook_cube")
    monthly.createOrReplaceTempView("monthly")
    total_cooks = cube_cook.agg(F.sum("cooks")).first()[0]
    by_type = {r["event_type"]: r["count"] for r in base.groupBy("event_type").count().collect()}
    report["inputs"] = {
        "events_path": f"{P.events}/events",
        "events": n_events, "events_before_join_users": ev_raw.count(), "dishes": n_dish,
        "active_users": base.select("user_id").distinct().count(),
        "months": sorted(r["month"] for r in base.select("month").distinct().collect()),
        "events_by_type": by_type,
        "check_cube_cook_total": total_cooks == by_type.get("cook"),
        "check_monthly_total": monthly.agg(F.sum(F.col("views") + F.col("favorites") + F.col("cooks")
                                                 + F.col("rates"))).first()[0] == n_events,
        "cube_cook_rows": cube_cook.count(), "monthly_rows": monthly.count(),
    }
    try:   # dung luong cac bang dang cache, lon nhat = bang co so (doi chieu voi tab Storage cua Spark UI)
        infos = spark.sparkContext._jsc.sc().getRDDStorageInfo()
        report["inputs"]["cache_mb_desc"] = sorted((round((i.memSize() + i.diskSize()) / 2**20, 1) for i in infos),
                                                   reverse=True)
    except Exception as e:  # noqa: BLE001
        print("[05] Khong doc duoc thong tin cache:", e)

# ===========================================================================
# 2. THOI GIAN: heatmap gio x thu, xu huong theo thang, mua/Tet, top mon theo bua
# ===========================================================================
with step("time"):
    # Luoi day du 7 x 24 o (gio khong co su kien -> 0) de dashboard ve heatmap khong bi thung
    heat = spark.sql("""
        WITH g AS (SELECT dow, hour,
                          count_if(event_type = 'view') AS views,
                          count_if(event_type = 'cook') AS cooks,
                          count(*)                      AS events
                   FROM ev GROUP BY dow, hour),
             k AS (SELECT int(d.id) AS dow, int(h.id) AS hour FROM range(1, 8) d CROSS JOIN range(0, 24) h)
        SELECT ((k.dow + 5) % 7) + 1 AS dow_idx,      -- 1 = T2 ... 7 = CN
               element_at(array('CN','T2','T3','T4','T5','T6','T7'), k.dow) AS dow_vn,
               k.hour,
               coalesce(g.views, 0) AS views, coalesce(g.cooks, 0) AS cooks, coalesce(g.events, 0) AS events
        FROM k LEFT JOIN g ON k.dow = g.dow AND k.hour = g.hour
    """)
    heat_rows = save(heat, "heatmap_hour_dow", order=["dow_idx", "hour"])
    report["heatmap_top_cook_cells"] = [f"{r['dow_vn']} {r['hour']}h: {r['cooks']}"
                                        for r in sorted(heat_rows, key=lambda r: -r["cooks"])[:5]]
    wk = {}
    for r in heat_rows:
        wk[r["dow_vn"]] = wk.get(r["dow_vn"], 0) + r["cooks"]
    report["cooks_by_dow"] = wk

    w_month = Window.partitionBy("month")
    trend = (monthly.groupBy("month", "dish_category")
             .agg(F.sum("views").alias("views"), F.sum("cooks").alias("cooks"))
             .withColumn("cook_share_pct", pct(F.col("cooks"), F.sum("cooks").over(w_month))))
    save(trend, "trend_month_category", order=["month", F.desc("cooks")])

    # Ti trong luot nau theo nhan mua cua mon (khong / nong / lanh / tet), theo thang va vung
    season_reg = monthly.groupBy("month", "region", "season").agg(F.sum("cooks").alias("cooks"))
    season_all = (monthly.groupBy("month", "season").agg(F.sum("cooks").alias("cooks"))
                  .withColumn("region", F.lit("Tất cả")))
    season = (season_reg.unionByName(season_all)
              .withColumn("share_pct", pct(F.col("cooks"), F.sum("cooks").over(Window.partitionBy("month", "region")))))
    season_rows = save(season, "season_month", order=["month", "region", "season"])
    report["season_share_pct_all_regions"] = {
        s: {r["month"]: r["share_pct"] for r in season_rows if r["region"] == "Tất cả" and r["season"] == s}
        for s in ("tết", "lạnh", "nóng")}

    # 2 cach xep hang moi bua:
    #   rk     : pho bien nhat (nhieu luot nau nhat) - thuong la cac mon pho bien chung, bua nao cung dung dau
    #   rk_lift: DAC TRUNG cua bua = lift cao nhat (ti trong trong bua / ti trong chung),
    #            chi xet 200 mon nau nhieu nhat cua bua de bo mon qua hiem
    top_slot = spark.sql("""
        WITH c AS (SELECT meal_slot, food_id, sum(cooks) AS cooks FROM cook_cube GROUP BY meal_slot, food_id),
             t AS (SELECT food_id, sum(cooks) / (SELECT sum(cooks) FROM cook_cube) AS share_all
                   FROM cook_cube GROUP BY food_id),
             r AS (SELECT c.*, t.share_all,
                          cooks / sum(cooks) OVER (PARTITION BY meal_slot) AS share,
                          row_number() OVER (PARTITION BY meal_slot ORDER BY cooks DESC, c.food_id) AS rk
                   FROM c JOIN t ON c.food_id = t.food_id),
             l AS (SELECT r.*, share / share_all AS lift,
                          CASE WHEN rk <= 200 THEN row_number() OVER (
                               PARTITION BY meal_slot, rk <= 200 ORDER BY share / share_all DESC, food_id) END AS rk_lift
                   FROM r)
        SELECT /*+ BROADCAST(d), BROADCAST(i) */
               l.meal_slot, l.rk, l.rk_lift, l.food_id, d.dish_name, d.dish_category, l.cooks,
               round(100 * l.share, 2) AS share_pct, round(l.lift, 3) AS lift, i.image_link
        FROM l JOIN dish d ON l.food_id = d.food_id
               LEFT JOIN food_img i ON l.food_id = i.food_id
        WHERE l.rk <= 10 OR l.rk_lift <= 10
    """)
    top_rows = save(top_slot, "top_dish_by_slot", order=["meal_slot", "rk"])
    slots = sorted({r["meal_slot"] for r in top_rows})
    report["top3_dish_by_slot"] = {s: [r["dish_name"] for r in top_rows if r["meal_slot"] == s][:3] for s in slots}
    report["top3_signature_dish_by_slot"] = {
        s: [f"{r['dish_name']} #{r['food_id']} (lift {r['lift']})"     # co mon trung ten -> kem food_id
            for r in sorted((r for r in top_rows if r["meal_slot"] == s and r["rk_lift"]), key=lambda r: r["rk_lift"])][:3]
        for s in slots}

    w_slot = Window.partitionBy("meal_slot")
    cat_slot = (cube_cook.groupBy("meal_slot", "dish_category").agg(F.sum("cooks").alias("cooks"))
                .withColumn("share_pct", pct(F.col("cooks"), F.sum("cooks").over(w_slot))))
    report["top_category_by_slot_cook_pct"] = {
        r["meal_slot"]: f"{r['dish_category']} {r['share_pct']}%"
        for r in cat_slot.withColumn("rk", F.row_number().over(w_slot.orderBy(F.desc("cooks"))))
                         .filter("rk = 1").collect()}

# ===========================================================================
# 3. KHAC BIET THEO NHOM: chi so lift = ti trong trong nhom / ti trong chung
#    lift 1,3 nghia la nhom do nau loai mon nay nhieu hon 30% so voi trung binh
# ===========================================================================
GROUPS = ["meal_slot", "day_type", "region", "age_group"]
ATTRS = ["dish_category", "main_protein", "main_method", "dish_type_fixed", "is_spicy", "is_quick"]


def lift_long(g, a):
    overall = (cube_cook.groupBy(a).agg(F.sum("cooks").alias("c_all"))
               .withColumn("overall_pct", 100 * F.col("c_all") / F.lit(total_cooks)))
    x = (cube_cook.groupBy(g, a).agg(F.sum("cooks").alias("cooks"))
         .withColumn("share_pct", 100 * F.col("cooks") / F.sum("cooks").over(Window.partitionBy(g))))
    return (x.join(overall, a)
            .select(F.lit(g).alias("group_type"), F.col(g).cast("string").alias("group_value"),
                    F.lit(a).alias("attribute"), F.col(a).cast("string").alias("value"), "cooks",
                    F.round("share_pct", 2).alias("share_pct"), F.round("overall_pct", 2).alias("overall_pct"),
                    F.round(F.col("share_pct") / F.col("overall_pct"), 3).alias("lift")))


with step("groups"):
    lift = reduce(lambda a, b: a.unionByName(b), [lift_long(g, a) for g in GROUPS for a in ATTRS])
    lift_rows = save(lift, "lift_by_group", order=["group_type", "group_value", "attribute", F.desc("lift")])
    # Noi bat: moi gia tri nhom lay 3 thuoc tinh co lift cao nhat (bo gia tri hiem < 2% va nhan "false")
    hl = {}
    for r in lift_rows:
        if r["overall_pct"] < 2 or r["value"] == "false" or r["attribute"] == "dish_type_fixed":
            continue
        hl.setdefault(f"{r['group_type']}={r['group_value']}", []).append(r)
    report["lift_highlights"] = {
        k: [f"{r['attribute']}={r['value']}: lift {r['lift']} ({r['share_pct']}% vs {r['overall_pct']}%)"
            for r in sorted(v, key=lambda r: -r["lift"])[:3]]
        for k, v in sorted(hl.items())}

# ===========================================================================
# 4. PHEU xem -> luu -> nau -> cham diem
#    Dem theo su kien thi 1 mon xem nhieu lan bi tinh nhieu lan, nen tinh them theo
#    CAP user-mon: trong cac cap da xem, bao nhieu % duoc luu / nau; trong cac cap da nau, % duoc cham.
# ===========================================================================
with step("funnel"):
    funnel_sql = """
        WITH pairs AS (SELECT DISTINCT user_id, food_id, event_type FROM ev),
        p AS (SELECT /*+ BROADCAST(d) */ d.dish_category,
                     count_if(event_type = 'view')     AS view_pairs,
                     count_if(event_type = 'favorite') AS favorite_pairs,
                     count_if(event_type = 'cook')     AS cook_pairs,
                     count_if(event_type = 'rate')     AS rate_pairs
              FROM pairs JOIN dish d ON pairs.food_id = d.food_id
              GROUP BY ROLLUP(d.dish_category)),
        e AS (SELECT dish_category, sum(views) AS view_events, sum(favorites) AS favorite_events,
                     sum(cooks) AS cook_events, sum(rates) AS rate_events,
                     round(try_divide(sum(rating_sum), sum(rates)), 3) AS avg_rating
              FROM monthly GROUP BY ROLLUP(dish_category))
        SELECT coalesce(p.dish_category, 'Tất cả') AS dish_category,
               view_events, favorite_events, cook_events, rate_events,
               view_pairs, favorite_pairs, cook_pairs, rate_pairs,
               round(100 * favorite_pairs / view_pairs, 2) AS favorite_per_view_pct,
               round(100 * cook_pairs / view_pairs, 2)     AS cook_per_view_pct,
               round(100 * rate_pairs / cook_pairs, 2)     AS rate_per_cook_pct,
               avg_rating
        FROM p JOIN e ON p.dish_category <=> e.dish_category
    """
    funnel = spark.sql(funnel_sql)
    funnel_rows = save(funnel, "funnel_by_category", order=[F.desc("view_pairs")])
    report["funnel_pairs_all"] = next(r.asDict() for r in funnel_rows if r["dish_category"] == "Tất cả")
    fu = spark.sql("""
        WITH u AS (SELECT user_id,
                          max(int(event_type = 'view')) AS v, max(int(event_type = 'favorite')) AS f,
                          max(int(event_type = 'cook')) AS c, max(int(event_type = 'rate')) AS r
                   FROM ev GROUP BY user_id)
        SELECT count(*) AS users, sum(v) AS viewed, sum(f) AS favorited, sum(c) AS cooked, sum(r) AS rated FROM u
    """).first().asDict()
    report["funnel_users"] = {**fu, **{f"{k}_pct": round(100 * fu[k] / fu["users"], 2)
                                       for k in ("viewed", "favorited", "cooked", "rated")}}

# ===========================================================================
# 5. MON VA NGUYEN LIEU
# ===========================================================================
SEASONINGS = ["muối", "dầu ăn", "đường", "đường trắng", "hạt nêm", "tiêu", "tiêu xay", "nước mắm", "bột ngọt",
              "nước tương", "nước", "dầu hào", "dầu mè", "giấm", "gia vị nêm sẵn", "dầu điều", "tương ớt",
              "rượu trắng", "bột năng", "bột bắp", "đường phèn", "ớt bột", "nước cốt chanh", "hạt nêm chay knorr nấm hương",
              "giấm gạo lên men ajinomoto", "bột nở", "vani", "tỏi băm", "hành tím băm", "hành tỏi băm", "ớt băm"]

with step("dishes"):
    dish_stats = (dish.join(monthly.groupBy("food_id")
                            .agg(*[F.sum(c).alias(c) for c in ("views", "favorites", "cooks", "rates", "rating_sum")]),
                            "food_id", "left")
                  .fillna(0, subset=["views", "favorites", "cooks", "rates", "rating_sum"])
                  # Spark 4 bat ANSI: chia cho 0 bao loi -> dung try_divide (mon chua ai cham -> null)
                  .withColumn("avg_rating", F.round(F.try_divide("rating_sum", "rates"), 3))
                  .drop("rating_sum")
                  .join(F.broadcast(foods.select("food_id", "image_link")), "food_id", "left")
                  .withColumn("cook_rank", F.row_number().over(Window.orderBy(F.desc("cooks"), "food_id")))
                  .persist())
    ds_rows = save(dish_stats, "dish_stats", order=["cook_rank"], json_limit=100)

    def catalog_vs(a):
        return (dish_stats.groupBy(a).agg(F.count("*").alias("n_dishes"), F.sum("cooks").alias("cooks"))
                .select(F.lit(a).alias("attribute"), F.col(a).cast("string").alias("value"), "n_dishes", "cooks",
                        pct(F.col("n_dishes"), F.lit(n_dish)).alias("catalog_pct"),
                        pct(F.col("cooks"), F.lit(total_cooks)).alias("cook_pct"),
                        F.round(F.col("cooks") / F.col("n_dishes"), 1).alias("cooks_per_dish")))

    cvc = reduce(lambda a, b: a.unionByName(b), [catalog_vs(a) for a in ("main_method", "dish_category", "main_protein")])
    cvc = cvc.withColumn("lift", F.round(F.col("cook_pct") / F.col("catalog_pct"), 3))
    cvc_rows = save(cvc, "catalog_vs_cooked", order=["attribute", F.desc("cooks")])
    report["main_method_catalog_vs_cooked"] = [
        f"{r['value']}: {r['catalog_pct']}% mon -> {r['cook_pct']}% luot nau (lift {r['lift']})"
        for r in cvc_rows if r["attribute"] == "main_method"]

    ing = (foods.select("food_id", F.explode("ingredient_list").alias("ing"))
           .select("food_id", F.lower(F.trim("ing")).alias("ingredient"))
           .filter(F.length("ingredient") > 0).distinct()
           .join(F.broadcast(dish_stats.select("food_id", "cooks")), "food_id")
           .groupBy("ingredient").agg(F.count("*").alias("n_dishes"), F.sum("cooks").alias("cooks"))
           .withColumn("is_seasoning", F.col("ingredient").isin(SEASONINGS))
           .withColumn("cook_rank", F.row_number().over(Window.orderBy(F.desc("cooks"), "ingredient"))))
    ing_rows = save(ing, "top_ingredients", order=["cook_rank"], json_limit=200)
    report["n_distinct_ingredients"] = len(ing_rows)
    report["top10_ingredients_not_seasoning"] = [f"{r['ingredient']} ({r['n_dishes']} mon, {r['cooks']} luot nau)"
                                                 for r in ing_rows if not r["is_seasoning"]][:10]

# ===========================================================================
# 6. HANH VI: diem cham, phien nau ("mam com"), nau lai, muc hoat dong, duoi dai
# ===========================================================================
with step("behavior"):
    rd = (base.filter("event_type = 'rate'").groupBy("rating").count()
          .withColumn("share_pct", pct(F.col("count"), F.sum("count").over(Window.partitionBy()))))
    save(rd, "rating_dist", order=["rating"])
    rs = base.filter("event_type = 'rate'").agg(F.round(F.avg("rating"), 3).alias("mean"),
                                                 F.round(F.stddev("rating"), 3).alias("std")).first()
    report["rating"] = rs.asDict()

    sess = (base.filter("event_type = 'cook'").groupBy("session_id")
            .agg(F.first("meal_slot").alias("meal_slot"), F.countDistinct("food_id").alias("n"))
            .withColumn("size", F.when(F.col("n") >= 4, "4+").otherwise(F.col("n").cast("string"))))
    ss = (sess.groupBy("meal_slot", "size").count()
          .unionByName(sess.groupBy("size").count().withColumn("meal_slot", F.lit("Tất cả")))
          .withColumn("share_pct", pct(F.col("count"), F.sum("count").over(Window.partitionBy("meal_slot")))))
    ss_rows = save(ss, "session_size", order=["meal_slot", "size"])
    report["cook_sessions_2plus_dishes_pct"] = {
        s: round(sum(r["share_pct"] for r in ss_rows if r["meal_slot"] == s and r["size"] != "1"), 2)
        for s in sorted({r["meal_slot"] for r in ss_rows})}

    pc = (base.filter("event_type = 'cook'").groupBy("user_id", "food_id").agg(F.count("*").alias("times"))
          .join(F.broadcast(dish.select("food_id", "dish_category")), "food_id"))
    rep = (pc.rollup("dish_category")
           .agg(F.count("*").alias("cooked_pairs"), F.sum((F.col("times") >= 2).cast("int")).alias("repeat_pairs"),
                F.round(F.avg("times"), 3).alias("avg_times"))
           .withColumn("dish_category", F.coalesce("dish_category", F.lit("Tất cả")))
           .withColumn("repeat_pct", pct(F.col("repeat_pairs"), F.col("cooked_pairs"))))
    rep_rows = save(rep, "repeat_by_category", order=[F.desc("repeat_pct")])
    report["repeat_cook_pct_all"] = next(r["repeat_pct"] for r in rep_rows if r["dish_category"] == "Tất cả")
    report["times_cooked_same_dish"] = {
        str(r["t"]): r["count"]
        for r in pc.groupBy(F.least("times", F.lit(5)).alias("t")).count().orderBy("t").collect()}

    BUCKETS = [(0, 0, "0"), (1, 5, "1-5"), (6, 20, "6-20"), (21, 50, "21-50"), (51, 100, "51-100"), (101, None, ">100")]
    bucket = F.lit(None)
    for i, (lo, hi, lab) in reversed(list(enumerate(BUCKETS))):
        cond = (F.col("cooks") >= lo) if hi is None else F.col("cooks").between(lo, hi)
        bucket = F.when(cond, F.struct(F.lit(i).alias("ord"), F.lit(lab).alias("label"))).otherwise(bucket)
    ua = (base.groupBy("user_id").agg(cnt("cook", "cooks"), F.count("*").alias("events"))
          .withColumn("b", bucket)
          .groupBy(F.col("b.ord").alias("ord"), F.col("b.label").alias("cooks_per_user"))
          .agg(F.count("*").alias("users"), F.round(F.avg("events"), 1).alias("avg_events"))
          .withColumn("share_pct", pct(F.col("users"), F.sum("users").over(Window.partitionBy()))))
    save(ua, "user_activity", order=["ord"])

    # Duoi dai: tinh tren driver (5.499 so) - Gini va duong cong tich luy cho dashboard
    def gini(xs):
        xs = sorted(xs)
        n, s = len(xs), sum(xs)
        return round(2 * sum((i + 1) * x for i, x in enumerate(xs)) / (n * s) - (n + 1) / n, 4) if s else None

    def cum_curve(xs, points=100):
        xs = sorted(xs, reverse=True)
        s, out, acc, j = sum(xs), [], 0, 0
        for p in range(1, points + 1):
            k = round(len(xs) * p / points)
            while j < k:
                acc += xs[j]
                j += 1
            out.append(round(100 * acc / s, 2) if s else 0.0)
        return out

    views_l = [r["views"] for r in ds_rows]
    cooks_l = [r["cooks"] for r in ds_rows]
    cv, cc = cum_curve(views_l), cum_curve(cooks_l)
    curve = spark.createDataFrame([(p + 1, cv[p], cc[p]) for p in range(100)],
                                  "dish_pct int, views_cum_pct double, cooks_cum_pct double")
    save(curve, "long_tail_curve", order=["dish_pct"])
    report["long_tail"] = {
        "gini_views": gini(views_l), "gini_cooks": gini(cooks_l),
        "top1pct_dishes_cook_share_pct": cc[0], "top10pct_dishes_cook_share_pct": cc[9],
        "top20pct_dishes_cook_share_pct": cc[19],
        "dishes_never_viewed": sum(1 for x in views_l if x == 0),
        "dishes_never_cooked": sum(1 for x in cooks_l if x == 0),
    }

# ===========================================================================
# 7. KE HOACH THUC THI (cho bao cao: broadcast join, partition pruning, ROLLUP)
# ===========================================================================
with step("explain"):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("=== Pheu theo nhom mon (Spark SQL, ROLLUP + broadcast join) ===")
        spark.sql(funnel_sql).explain(mode="formatted")
        print("\n=== Loc theo thang (partition pruning: chi doc thu muc month=2026-09) ===")
        ev_raw.filter("month = '2026-09' AND event_type = 'cook'").groupBy("food_id").count().explain(mode="formatted")
    with open(os.path.join(OUT_LOCAL, "explain.txt"), "w", encoding="utf-8") as fh:
        fh.write(buf.getvalue())

report["note"] = ("Dữ liệu hành vi là MÔ PHỎNG (bước 04). Kết quả kiểm chứng pipeline tìm lại được quy luật đã cài, "
                  "không phải phát hiện về người dùng thật. Số liệu tính trên toàn bộ 12 tháng.")
report["tables"] = tables
report["timings_s"] = timings
report["total_seconds"] = round(time.time() - t0, 1)
report["mode"] = "local" if args.local else "cluster"
with open(os.path.join(P.output_local, "analysis_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2, default=str)

print(json.dumps({k: report[k] for k in ["inputs", "funnel_users", "long_tail", "tables", "timings_s",
                                          "total_seconds"]}, ensure_ascii=False, indent=2, default=str))
spark.stop()
