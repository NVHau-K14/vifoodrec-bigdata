"""
06f_hybrid.py - Mo hinh chinh: hybrid gop 4 nguon bang weighted RRF + luat cold-start, danh gia cuoi tren test (D12).

Nguon (cung do sau 100, tu 06b va 06c): als_implicit, content, pop_vung_tuoi, nau_lai
  score(u, i) = alpha/(60 + hang_als) + beta/(60 + hang_content) + gamma/(60 + hang_pop) + delta/(60 + hang_nau_lai)
  (mon khong co trong nguon -> dong gop 0)
Do trong so: luoi alpha+beta+gamma+delta = 1, buoc 0,1 (286 to hop), toi da NDCG@10 cua user AM trong mau
  10.000 user cua val. Bang ung vien do Spark tao, vong do luoi chay bang numpy tren driver (D12).
Cold-start theo nhom user cua 06a: lanh -> pop_vung_tuoi; it -> chon giua "giu trong so" va "alpha = 0"
  (so tren moi user 'it' cua val); am -> hybrid day du.
"hybrid + content 2 vi tri" (hybrid_c2, D13): vi tri 1-8 tu hybrid; vi tri 9 = mon content user CHUA nau,
  diem content x log1p(luot nau trong lich su); vi tri 10 = mon content chua nau va IT tuong tac (luot nau
  <= phan vi 20% cua cac mon), theo diem content; phan sau la hybrid tiep. recs_final dung ban nay.

Danh gia (view test, tham so lay tu val):
  - bang chinh: moi mo hinh tren CUNG tap user, tach nhom tat ca / am / it / lanh
  - bien the "kham pha": bo mon user da nau trong lich su khoi goi y va dap an
  - coverage, novelty, diversity (1 - Jaccard tap token cua 06c) tren top 10
  - khoang tin cay 95% cua hieu NDCG@10 ghep cap (hybrid so voi tung mo hinh; tat ca va chi user am)
  - thi nghiem mon moi: an lich su cua 300 mon, fit lai ALS, do kha nang goi y ra cac mon do

Dau vao : /data/results/models/{recs_*,truth,user_groups,implicit,item_pop,item_tokens,item_sim}_<v>
Dau ra  : /data/results/models/recs_hybrid_<v>, eval_hybrid_<v>, recs_hybrid_c2_<v>, eval_hybrid_c2_<v>
          /data/results/models/recs_final  (user_id, rank, food_id, score, source, reason_type,
                                            because_food_id, reason) top 50 cho MOI user - buoc 07 xuat MongoDB
          /data/results/models/metrics     bang tong hop (model, variant, group, do do)
          data/output/model_hybrid_report.json, data/output/models_metrics.json

Chay tren cum:  python src/06f_hybrid.py           (--no-cold-items: bo thi nghiem mon moi)
Chay thu local: python src/06f_hybrid.py --local
"""
import itertools
import json
import os
import sys

import numpy as np
from pyspark.ml.recommendation import ALS
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06f_hybrid", __doc__,
                         extra=lambda ap: ap.add_argument("--no-cold-items", action="store_true",
                                                          help="bo qua thi nghiem mon moi"))
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
if not args.local:
    spark.conf.set("spark.sql.shuffle.partitions", "32")
T = R.Timer()
report = {"mode": "local" if args.local else "cluster"}
SOURCES = {"als": "als_implicit", "content": "content", "pop": "pop_vung_tuoi", "rep": "nau_lai"}
KRRF, N_OUT, N_FINAL = 60, 100, 50
LOW_POP_Q = 0.2          # mon 'it tuong tac': luot nau trong lich su <= phan vi 20% cua cac mon
BASE_MODELS = ["random", "pop_chung", "pop_gan_day", "pop_vung_tuoi", "nau_lai", "als_implicit", "content"]


def candidates(v, users=None):
    """Hop top-100 cua 4 nguon -> 1 dong / (user, mon), cot f_<nguon> = 1/(60 + hang) hoac 0."""
    parts = []
    for s, name in SOURCES.items():
        d = R.load(spark, P, f"recs_{name}", v).select("user_id", "food_id", "rank", *(
            ["because_food_id"] if name == "content" else []))
        if users is not None:
            d = d.join(users, "user_id")
        parts.append(d.select("user_id", "food_id", F.lit(s).alias("src"), "rank",
                              (F.col("because_food_id") if name == "content" else F.lit(None).cast("int")).alias("because")))
    u = parts[0]
    for p in parts[1:]:
        u = u.unionByName(p)
    return (u.groupBy("user_id", "food_id").agg(
        *[F.max(F.when(F.col("src") == s, 1.0 / (KRRF + F.col("rank")))).alias(f"f_{s}") for s in SOURCES],
        F.max("because").alias("because_food_id"))
        .fillna(0.0, [f"f_{s}" for s in SOURCES]))


def score_expr(w):
    return sum(F.lit(float(w[s])) * F.col(f"f_{s}") for s in SOURCES)


# ===========================================================================
# 1. DO TRONG SO TREN VAL (numpy tren driver)
# ===========================================================================
def to_numpy(cand, truth):
    lab = truth.select("user_id", F.explode("items").alias("food_id")).withColumn("label", F.lit(1.0))
    pdf = (cand.join(lab, ["user_id", "food_id"], "left").fillna(0.0, ["label"])
           .select("user_id", *[F.col(f"f_{s}").cast("float") for s in SOURCES], F.col("label").cast("float"))
           .toPandas())
    nt = truth.select("user_id", F.size("items").alias("n")).toPandas()
    uids = np.sort(nt["user_id"].to_numpy())
    uidx = np.searchsorted(uids, pdf["user_id"].to_numpy())
    order = np.argsort(uidx, kind="stable")
    X = pdf[[f"f_{s}" for s in SOURCES]].to_numpy()[order]
    y = pdf["label"].to_numpy()[order]
    uidx = uidx[order]
    n = nt.set_index("user_id").loc[uids, "n"].to_numpy()
    idcg = np.array([sum(1 / np.log2(i + 2) for i in range(min(10, k))) for k in n])
    starts = np.concatenate([[0], np.cumsum(np.bincount(uidx, minlength=len(uids)))[:-1]])
    return {"X": X, "y": y, "u": uidx, "idcg": idcg, "starts": starts, "n_users": len(uids)}


def ndcg10(d, w):
    s = d["X"] @ np.asarray(w, dtype=np.float64)
    o = np.lexsort((-s, d["u"]))
    u, y = d["u"][o], d["y"][o]
    pos = np.arange(len(o)) - d["starts"][u]
    m = pos < 10
    dcg = np.bincount(u[m], weights=y[m] / np.log2(pos[m] + 2), minlength=d["n_users"])
    return float((dcg / d["idcg"]).mean())


with T("tune_weights"):
    tv = R.load(spark, P, "truth", "val")
    tune = tv.filter("tune AND group = 'ấm'")
    d = to_numpy(candidates("val", tune.select("user_id")), tune)
    grid = [(a / 10, b / 10, c / 10, (10 - a - b - c) / 10)
            for a, b, c in itertools.product(range(11), repeat=3) if a + b + c <= 10]
    res = sorted(((ndcg10(d, w), w) for w in grid), reverse=True)
    best_w = dict(zip(SOURCES, res[0][1]))
    report["tuning"] = {"users": d["n_users"], "candidate_rows": int(len(d["y"])), "combos": len(grid),
                        "candidate_recall_pct": round(100 * float(d["y"].sum()) / float(
                            tune.select(F.sum(F.size("items"))).first()[0]), 2),
                        "top5": [{"w": dict(zip(SOURCES, w)), "ndcg@10": round(s, 4)} for s, w in res[:5]],
                        "single_source": {s: round(ndcg10(d, [1.0 if k == s else 0.0 for k in SOURCES]), 4)
                                          for s in SOURCES}}
    report["best_weights"] = best_w
    print(f"[06] best weights {best_w} ndcg@10 = {res[0][0]:.4f}", flush=True)

    # Nhom 'it': giu trong so hay alpha = 0 (so tren moi user 'it' cua val)
    few = tv.filter("group = 'ít'")
    df_ = to_numpy(candidates("val", few.select("user_id")), few)
    w_no_als = dict(best_w, als=0.0)
    s_ = sum(w_no_als.values()) or 1.0
    w_no_als = {k: x / s_ for k, x in w_no_als.items()} if sum(w_no_als.values()) else {"als": 0, "content": 0, "pop": 1, "rep": 0}
    a1, a2 = ndcg10(df_, [best_w[s] for s in SOURCES]), ndcg10(df_, [w_no_als[s] for s in SOURCES])
    few_w = best_w if a1 >= a2 else w_no_als
    report["few_users_rule"] = {"users": df_["n_users"], "giu_trong_so": round(a1, 4), "alpha_0": round(a2, 4),
                                "chon": "giữ trọng số" if a1 >= a2 else "alpha = 0", "weights": few_w}
COLD_W = {"als": 0.0, "content": 0.0, "pop": 1.0, "rep": 0.0}


def hybrid(v, users):
    """users: (user_id, group). Tra ve top-N_OUT hybrid voi trong so theo nhom."""
    c = candidates(v, users.select("user_id")).join(users, "user_id")
    sc = (F.when(F.col("group") == "lạnh", score_expr(COLD_W))
          .when(F.col("group") == "ít", score_expr(few_w)).otherwise(score_expr(best_w)))
    contrib = {s: F.col(f"f_{s}") * F.when(F.col("group") == "lạnh", COLD_W[s])
               .when(F.col("group") == "ít", few_w[s]).otherwise(best_w[s]) for s in SOURCES}
    top_src = F.element_at(F.array(*[F.lit(s) for s in SOURCES]),
                           F.array_position(F.array(*contrib.values()), F.greatest(*contrib.values())).cast("int"))
    return R.top_n(c.withColumn("score", sc).withColumn("source", top_src), N_OUT)


# ===========================================================================
# 2. GOI Y HYBRID + DANH GIA MOI MO HINH
# ===========================================================================
def explore_eval(recs, truth, cooked):
    """Bien the kham pha: bo mon da nau trong lich su khoi goi y (xep hang lai) va khoi dap an."""
    r = R.top_n(recs.join(cooked, ["user_id", "food_id"], "left_anti").withColumn("s", -F.col("rank")), 10, "s")
    t = (truth.select("user_id", "group", F.explode("items").alias("food_id"))
         .join(cooked, ["user_id", "food_id"], "left_anti")
         .groupBy("user_id", "group").agg(F.array_sort(F.collect_list("food_id")).alias("items")))
    return R.per_user_metrics(r, t)


def content_slots(hyb, con, cooked, ipop, thr):
    """
    hybrid + content 2 vi tri: giu vi tri 1-8 cua hybrid, chen 2 mon content vao vi tri 9-10, day phan con lai.
      hyb : (user_id, food_id, rank, source)    con: (user_id, food_id, score) - diem content cua user
      cooked: (user_id, food_id) mon user da nau  ipop: (food_id, cooks) luot nau trong lich su  thr: nguong 'it'
    Vi tri 9: diem content x log1p(cooks) ; vi tri 10: mon co cooks <= thr, theo diem content
    (khong co thi lay mon thu 2 cua vi tri 9).
    """
    top8 = hyb.filter("rank <= 8").select("user_id", "food_id")
    c = (con.select("user_id", "food_id", "score")
         .join(cooked, ["user_id", "food_id"], "left_anti").join(top8, ["user_id", "food_id"], "left_anti")
         .join(F.broadcast(ipop.select("food_id", "cooks")), "food_id", "left").fillna(0, ["cooks"]).cache())
    s9 = R.top_n(c.select("user_id", "food_id", (F.col("score") * F.log1p("cooks")).alias("score")), 2)
    s10 = R.top_n(c.filter(F.col("cooks") <= thr).select("user_id", "food_id", "score"), 2)
    cand = (s9.filter("rank = 1").select("user_id", "food_id", F.lit(1).alias("pri"))
            .unionByName(s10.select("user_id", "food_id", (1 + F.col("rank")).alias("pri")))      # 2, 3
            .unionByName(s9.filter("rank = 2").select("user_id", "food_id", F.lit(4).alias("pri")))  # du phong
            .groupBy("user_id", "food_id").agg(F.min("pri").alias("pri")))
    picks = R.top_n(cand.withColumn("s", -F.col("pri").cast("double")), 2, "s").select(
        "user_id", "food_id", (8 + F.col("rank")).alias("pos"), F.lit("content_slot").alias("source"))
    npk = picks.groupBy("user_id").agg(F.count("*").alias("k"))
    rest = (hyb.join(picks.select("user_id", "food_id"), ["user_id", "food_id"], "left_anti")
            .withColumn("r", F.row_number().over(Window.partitionBy("user_id").orderBy("rank")))
            .join(npk, "user_id", "left").fillna(0, ["k"])
            .select("user_id", "food_id", "source",
                    F.when(F.col("r") <= 8, F.col("r")).otherwise(F.col("r") + F.col("k")).alias("pos")))
    return (rest.unionByName(picks.select("user_id", "food_id", "source", "pos"))
            .filter(F.col("pos") <= N_OUT).withColumnRenamed("pos", "rank")
            .withColumn("score", -F.col("rank").cast("double")))


def low_pop_threshold(ipop):
    return ipop.approxQuantile("cooks", [LOW_POP_Q], 0.0)[0]


rows, ci = [], []
thr_by_view = {}
for v in ("val", "test"):
    with T(f"{v}:hybrid"):
        truth = R.load(spark, P, "truth", v).cache()
        ug = R.load(spark, P, "user_groups", v)
        users = (truth.select("user_id") if v == "val" else ug.select("user_id")).join(ug.select("user_id", "group"), "user_id")
        R.save(hybrid(v, users).select("user_id", "food_id", "rank", "score", "source", "because_food_id"),
               P, "recs_hybrid", v)
        R.save(R.per_user_metrics(R.load(spark, P, "recs_hybrid", v), truth), P, "eval_hybrid", v)
    with T(f"{v}:hybrid_c2"):
        ipop_v = R.load(spark, P, "item_pop", v)
        thr_by_view[v] = low_pop_threshold(ipop_v)
        cooked_v = R.load(spark, P, "implicit", v).filter("n_cook > 0").select("user_id", "food_id")
        c2 = content_slots(R.load(spark, P, "recs_hybrid", v), R.load(spark, P, "recs_content", v),
                           cooked_v, ipop_v, thr_by_view[v])
        R.save(c2, P, "recs_hybrid_c2", v)
        R.save(R.per_user_metrics(R.load(spark, P, "recs_hybrid_c2", v), truth), P, "eval_hybrid_c2", v)
    models = BASE_MODELS + ["hybrid", "hybrid_c2"]
    with T(f"{v}:metrics"):
        for m in models:
            for g in R.summarize(R.load(spark, P, f"eval_{m}", v)):
                rows.append({"view": v, "model": m, "variant": "chính", **g})
    if v != "test":
        continue
    with T("test:explore_beyond"):
        cooked = R.load(spark, P, "implicit", v).filter("n_cook > 0").select("user_id", "food_id").cache()
        ipop = R.load(spark, P, "item_pop", v)
        tot, n_items = ipop.agg(F.sum("cooks"), F.count("*")).first()
        nov = F.broadcast(ipop.select("food_id", (-F.log2((F.col("cooks") + 1) / F.lit(tot + n_items))).alias("nov")))
        toks = F.broadcast(R.load(spark, P, "item_tokens"))
        tusers = truth.select("user_id")
        for m in models:
            recs = R.load(spark, P, f"recs_{m}", v).select("user_id", "food_id", "rank")
            for g in R.summarize(explore_eval(recs, truth, cooked)):
                rows.append({"view": v, "model": m, "variant": "khám phá", **g})
            t10 = recs.filter("rank <= 10").join(tusers, "user_id").cache()
            pairs = (t10.alias("a").join(t10.alias("b"), (F.col("a.user_id") == F.col("b.user_id"))
                                          & (F.col("a.food_id") < F.col("b.food_id")))
                     .select(F.col("a.user_id").alias("user_id"), F.col("a.food_id").alias("i"), F.col("b.food_id").alias("j"))
                     .join(toks.select(F.col("food_id").alias("i"), F.col("tokens").alias("ti")), "i")
                     .join(toks.select(F.col("food_id").alias("j"), F.col("tokens").alias("tj")), "j")
                     .withColumn("jac", F.size(F.array_intersect("ti", "tj")) / F.size(F.array_union("ti", "tj"))))
            div = pairs.groupBy("user_id").agg(F.avg(1 - F.col("jac")).alias("d")).agg(F.avg("d")).first()[0]
            rows.append({"view": v, "model": m, "variant": "ngoài độ chính xác", "group": "tất cả",
                         "coverage_pct": round(100 * t10.select("food_id").distinct().count() / n_items, 2),
                         "novelty": round(t10.join(nov, "food_id").agg(F.avg("nov")).first()[0], 3),
                         "diversity": round(div, 4) if div is not None else None})
            t10.unpersist()
    with T("test:ci"):
        eh = R.load(spark, P, "eval_hybrid", v)
        warm = truth.filter("group = 'ấm'").select("user_id")
        for m in ("als_implicit", "content", "nau_lai", "pop_vung_tuoi", "pop_gan_day"):
            em = R.load(spark, P, f"eval_{m}", v)
            ci.append({**R.paired_ci(eh, em, name_a="hybrid", name_b=m), "users": "tất cả"})
            ci.append({**R.paired_ci(eh, em, name_a="hybrid", name_b=m, where=warm), "users": "ấm"})
        ec2 = R.load(spark, P, "eval_hybrid_c2", v)
        ci.append({**R.paired_ci(ec2, eh, name_a="hybrid_c2", name_b="hybrid"), "users": "tất cả"})
        ci.append({**R.paired_ci(ec2, eh, name_a="hybrid_c2", name_b="hybrid", where=warm), "users": "ấm"})
        ea = R.load(spark, P, "eval_als_implicit", v)
        ci.append({**R.paired_ci(ea, R.load(spark, P, "eval_nau_lai", v), name_a="als_implicit", name_b="nau_lai"),
                   "users": "tất cả"})
    truth.unpersist()

report["low_pop_threshold_cooks"] = thr_by_view
report["metrics"] = rows
report["ci95_test_ndcg@10"] = ci

# ===========================================================================
# 3. GOI Y CUOI CHO MOI USER (view test = lich su train + val) -> buoc 07
# ===========================================================================
with T("final_recs"):
    ug = R.load(spark, P, "user_groups", "test")
    imp = R.load(spark, P, "implicit", "test").select("user_id", "food_id", "n_cook")
    try:
        names = spark.read.parquet(f"{P.features}/dish_features").select("food_id", "dish_name")
    except Exception:
        names = spark.read.parquet("file://" + os.path.join(P.processed_local, "dish_features.parquet")).select("food_id", "dish_name")
    names = F.broadcast(names)
    # Ly do cho vi tri content: mon DA NAU cua user giong mon duoc goi y nhat (theo item_sim);
    # khong co thi dung mon dong gop nhieu nhat cua 06c (co the chi la mon da xem)
    c2t = R.load(spark, P, "recs_hybrid_c2", "test").filter(F.col("rank") <= N_FINAL)
    picks = c2t.filter("source = 'content_slot'").select("user_id", "food_id")
    sim = F.broadcast(R.load(spark, P, "item_sim").select(F.col("food_id").alias("j"),
                                                          F.col("sim_food_id").alias("food_id"), "sim"))
    bc = (picks.join(imp.filter("n_cook > 0").select("user_id", F.col("food_id").alias("j")), "user_id")
          .join(sim, ["j", "food_id"]).groupBy("user_id", "food_id").agg(F.max_by("j", "sim").alias("because_cooked")))
    bv = R.load(spark, P, "recs_content", "test").select("user_id", "food_id",
                                                         F.col("because_food_id").alias("because_viewed"))
    hb = R.load(spark, P, "recs_hybrid", "test").select("user_id", "food_id", F.col("because_food_id").alias("because_h"),
                                                        F.round("score", 6).alias("score"))
    c2t = (c2t.drop("score").join(bc, ["user_id", "food_id"], "left").join(bv, ["user_id", "food_id"], "left")
           .join(hb, ["user_id", "food_id"], "left")      # diem hybrid goc (vi tri content co the null)
           .withColumn("because_food_id", F.coalesce("because_cooked", "because_viewed", "because_h"))
           .withColumn("because_is_cooked", F.col("because_cooked").isNotNull()))
    fin = (c2t
           .join(ug.select("user_id", "region", "age_group"), "user_id")
           .join(imp, ["user_id", "food_id"], "left")
           .join(names.select(F.col("food_id").alias("because_food_id"), F.col("dish_name").alias("because_name")),
                 "because_food_id", "left")
           .withColumn("reason_type", F.col("source"))
           .withColumn("reason", F.when(F.col("source") == "als", F.lit("Người có khẩu vị giống bạn cũng hay nấu món này"))
                       .when(F.col("source").isin("content", "content_slot"),
                             F.concat(F.lit("Giống món "), F.coalesce("because_name", F.lit("bạn từng chọn")),
                                      F.when(F.col("because_is_cooked"), F.lit(" bạn đã nấu")).otherwise(F.lit(" bạn đã xem"))))
                       .when(F.col("source") == "rep", F.concat(F.lit("Bạn đã nấu món này "), F.col("n_cook").cast("string"), F.lit(" lần")))
                       .otherwise(F.concat(F.lit("Đang được nhiều người "), F.col("age_group"), F.lit(" tuổi ở miền "),
                                           F.col("region"), F.lit(" nấu"))))
           .select("user_id", "rank", "food_id", "score", "source", "reason_type",
                   "because_food_id", "reason"))
    R.save(fin, P, "recs_final")
    fin = R.load(spark, P, "recs_final")
    report["final_recs"] = {"users": fin.select("user_id").distinct().count(), "rows": fin.count(),
                            "by_source": {r["source"]: r["count"] for r in fin.groupBy("source").count().collect()},
                            "content_slot_because_cooked_pct": round(100 * c2t.filter("source = 'content_slot'").agg(
                                F.avg(F.col("because_is_cooked").cast("int"))).first()[0], 2)}

# ===========================================================================
# 4. THI NGHIEM MON MOI (uu tien thap): an lich su cua 300 mon
# ===========================================================================
if not args.no_cold_items:
    with T("cold_items"):
        v = "test"
        b = json.load(open(os.path.join(P.output_local, "model_als_report.json"), encoding="utf-8"))["best_als_implicit"]
        hidden = (R.load(spark, P, "item_pop", v).select("food_id")
                  .orderBy(F.xxhash64("food_id", F.lit(R.SEED + 1))).limit(300).cache())
        truth = R.load(spark, P, "truth", v)
        tp = truth.select("user_id", F.explode("items").alias("food_id")).join(hidden, "food_id")
        hu = tp.select("user_id").distinct().cache()
        imp_f = R.load(spark, P, "implicit", v).join(hidden, "food_id", "left_anti")
        m = ALS(userCol="user_id", itemCol="food_id", ratingCol="conf", implicitPrefs=True, alpha=float(b["alpha"]),
                rank=b["rank"], regParam=b["regParam"], maxIter=10, seed=R.SEED, checkpointInterval=5,
                coldStartStrategy="drop").fit(imp_f.select("user_id", "food_id", R.conf_expr().alias("conf")))
        als_c = (m.recommendForUserSubset(hu, N_OUT).select("user_id", F.posexplode("recommendations").alias("pos", "r"))
                 .select("user_id", F.col("r.food_id").alias("food_id"), (F.col("pos") + 1).alias("rank")))
        sim = R.load(spark, P, "item_sim")
        hist = R.top_n(imp_f.join(hu, "user_id").select("user_id", "food_id", R.conf_expr().alias("score")), 30)
        con_c = R.top_n(hist.select("user_id", F.col("food_id").alias("src"), F.col("score").alias("conf"))
                        .join(F.broadcast(sim.select(F.col("food_id").alias("src"), F.col("sim_food_id").alias("food_id"), "sim")), "src")
                        .groupBy("user_id", "food_id").agg(F.sum(F.col("conf") * F.col("sim")).alias("score")), N_OUT)
        drop_h = lambda d: d.join(hu, "user_id").join(hidden, "food_id", "left_anti")  # noqa: E731
        src = {"als": als_c, "content": con_c.select("user_id", "food_id", "rank"),
               "pop": drop_h(R.load(spark, P, "recs_pop_vung_tuoi", v)).select("user_id", "food_id", "rank"),
               "rep": drop_h(R.load(spark, P, "recs_nau_lai", v)).select("user_id", "food_id", "rank")}
        u = None
        for s, d0 in src.items():
            d0 = d0.select("user_id", "food_id", F.lit(s).alias("src"), "rank")
            u = d0 if u is None else u.unionByName(d0)
        cand = (u.groupBy("user_id", "food_id")
                .agg(*[F.max(F.when(F.col("src") == s, 1.0 / (KRRF + F.col("rank")))).alias(f"f_{s}") for s in SOURCES])
                .fillna(0.0))
        src["hybrid"] = R.top_n(cand.withColumn("score", score_expr(best_w)), N_OUT).select("user_id", "food_id", "rank")
        ipop_f = (R.load(spark, P, "item_pop", v).select("food_id")
                  .join(imp_f.groupBy("food_id").agg(F.sum("n_cook").alias("cooks")), "food_id", "left").fillna(0, ["cooks"]))
        src["hybrid_c2"] = content_slots(src["hybrid"].withColumn("source", F.lit("hybrid")), con_c,
                                         imp_f.filter("n_cook > 0").select("user_id", "food_id"), ipop_f,
                                         low_pop_threshold(ipop_f)).select("user_id", "food_id", "rank")
        n_pairs = tp.count()
        res = {}
        for s, d0 in src.items():
            hits = d0.join(tp, ["user_id", "food_id"])
            res[s] = {"hidden_recall@10": round(hits.filter("rank <= 10").count() / n_pairs, 4),
                      "hidden_recall@100": round(hits.count() / n_pairs, 4)}
        report["cold_items"] = {"hidden_items": 300, "test_pairs_with_hidden_items": n_pairs,
                                "users": hu.count(), "by_source": res}
        print(f"[06] cold items {report['cold_items']}", flush=True)

report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "hybrid", report)
with open(os.path.join(P.output_local, "models_metrics.json"), "w", encoding="utf-8") as fh:
    json.dump({"note": "Dữ liệu hành vi MÔ PHỎNG. Mọi mô hình xếp hạng chấm trên cùng tập user (D12).",
               "ranking": rows, "ci95_test_ndcg@10": ci}, fh, ensure_ascii=False, indent=1, default=str)
# Bang tong hop tren HDFS: cot co dinh + 1 cot JSON (cac dong co bo do do khac nhau)
R.save(spark.createDataFrame([(r["view"], r["model"], r["variant"], r["group"], json.dumps(r, ensure_ascii=False, default=str))
                              for r in rows], "view string, model string, variant string, group string, metrics string"),
       P, "metrics", coalesce=1)
spark.stop()
