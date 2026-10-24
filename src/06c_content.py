"""
06c_content.py - Goi y theo noi dung: TF-IDF tren token cua mon, do tuong tu chinh xac (phan tan)
                 va MinHashLSH (xap xi), goi y cho user tu lich su (D12, sua doi c, d).

Token cua 1 mon:
  - am tiet cua ten mon + tags: RegexTokenizer(pattern="[^\\p{L}\\p{M}]+") + StopWordsRemover (danh sach tu viet)
  - MOI nguyen lieu la 1 token, noi bang "_" (vd "nl:hành_lá"), bo gia vi (danh sach SEASONINGS)
  - dac trung co cau truc thanh token: "cat=canh/súp", "protein=hải sản", "method=xào", "type=Món chay",
    "season=tết", "tag=cay", "tag=nhanh", "tag=chay"
Vector: CountVectorizer(minDF=2, binary) -> IDF -> Normalizer (pipeline luu o /data/models/content_pipeline).

Do tuong tu CHINH XAC tinh phan tan bang chi muc nguoc (khong UDF): bang dai (food_id, token, w) voi
  w = idf / ||idf||  (idf = log((N+1)/(df+1)) nhu IDF cua Spark, tf nhi phan)
  -> self-join theo token -> cosine = sum(w_a * w_b), so token chung -> Jaccard.
MinHashLSH tren vector nhi phan (tap token): approxSimilarityJoin, do recall@20 so voi Jaccard chinh xac
  va so thoi gian. Khong dung BucketedRandomProjectionLSH tren vector thua nhieu chieu (D12, sua doi c).

Goi y cho user: 30 mon co do tin cay implicit cao nhat trong lich su,
  score(u, i) = sum_j conf_uj * cos(j, i) tren 50 mon tuong tu nhat cua j; giu mon j dong gop nhieu nhat (ly do).

Dau vao : /data/curated/foods, /data/features/dish_features, /data/results/models/{implicit,truth}_<v> (06a)
Dau ra  : /data/models/content_pipeline
          /data/results/models/item_tokens   (food_id, tokens)       - dung cho diversity o 06f
          /data/results/models/item_sim      (food_id, sim_food_id, sim, jaccard, rank) top 50 theo cosine
          /data/results/models/recs_content_<v>  (user_id, food_id, rank, score, because_food_id)
          /data/results/models/eval_content_<v>  do do tung user
          data/output/model_content_report.json

Chay tren cum:  python src/06c_content.py
Chay thu local: python src/06c_content.py --local
"""
import os
import sys
import time

from pyspark.ml import Pipeline
from pyspark.ml.feature import IDF, CountVectorizer, MinHashLSH, Normalizer, RegexTokenizer, StopWordsRemover
from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rec_common as R  # noqa: E402

args, spark, P = R.setup("06c_content", __doc__)
if not args.local:
    spark.conf.set("spark.sql.shuffle.partitions", "64")    # join tuong tu + goi y cho ~50k user
T = R.Timer()
report = {"mode": "local" if args.local else "cluster"}
N_SIM, N_HIST, N_REC = 50, 30, 100

# Tu dung: tu noi, tu chung cua ten mon (khong mang thong tin ve mon)
STOPWORDS = ["và", "với", "của", "cho", "các", "những", "một", "món", "cách", "làm", "kiểu", "ngon", "đơn", "giản",
             "tại", "nhà", "siêu", "cực", "thơm", "lạ", "miệng", "đẹp", "mắt", "dễ", "nhanh", "gọn", "chuẩn", "vị",
             "theo", "phong", "cách", "đậm", "đà", "bổ", "dưỡng", "hấp", "dẫn", "mới", "lạ", "the", "and", "with"]
SEASONINGS = R.SEASONINGS


def read_or_local(path, local_file):
    try:
        return spark.read.parquet(path)
    except Exception:
        if not args.local:
            raise
        return spark.read.parquet("file://" + os.path.join(P.processed_local, local_file))


# ===========================================================================
# 1. TOKEN VA VECTOR CUA MON
# ===========================================================================
with T("tokens"):
    foods = read_or_local(f"{P.curated}/foods", "foods_v2.parquet").select("food_id", "dish_name", "dish_tags",
                                                                          "ingredient_list")
    feat = read_or_local(f"{P.features}/dish_features", "dish_features.parquet")
    df = (foods.join(feat.drop("dish_name"), "food_id")
          .withColumn("text", F.concat_ws(" ", "dish_name", F.array_join(F.coalesce("dish_tags", F.array()), " "))))
    tok = RegexTokenizer(inputCol="text", outputCol="w_raw", pattern=r"[^\p{L}\p{M}]+", toLowercase=True)
    sw = StopWordsRemover(inputCol="w_raw", outputCol="w", stopWords=STOPWORDS)
    df = sw.transform(tok.transform(df))
    seas = F.array(*[F.lit(s) for s in SEASONINGS])
    ing = F.expr("transform(filter(transform(ingredient_list, x -> lower(trim(x))), x -> length(x) > 0), "
                 "x -> x)")
    df = (df.withColumn("ing", F.array_except(F.array_distinct(ing), seas))
          .withColumn("ing_tok", F.expr("transform(ing, x -> concat('nl:', regexp_replace(x, '\\\\s+', '_')))"))
          .withColumn("attr_tok", F.filter(F.array(
              F.concat(F.lit("cat="), "dish_category"), F.concat(F.lit("protein="), "main_protein"),
              F.concat(F.lit("method="), "main_method"), F.concat(F.lit("type="), "dish_type_fixed"),
              F.when(F.col("season") != "không", F.concat(F.lit("season="), "season")),
              F.when(F.col("is_spicy"), F.lit("tag=cay")), F.when(F.col("is_quick"), F.lit("tag=nhanh")),
              F.when(F.col("is_vegetarian"), F.lit("tag=chay"))), lambda x: x.isNotNull()))
          .withColumn("tokens", F.array_distinct(F.concat("w", "ing_tok", "attr_tok")))
          .select("food_id", "dish_name", "tokens").cache())
    n_items = df.count()

    pipe = Pipeline(stages=[CountVectorizer(inputCol="tokens", outputCol="tf", minDF=2, binary=True),
                            IDF(inputCol="tf", outputCol="tfidf"),
                            Normalizer(inputCol="tfidf", outputCol="vec", p=2.0)]).fit(df)
    pipe.write().overwrite().save(f"{P.models}/content_pipeline")
    vocab = pipe.stages[0].vocabulary
    vec = pipe.transform(df).select("food_id", "dish_name", "tokens", "tf", "vec").cache()
    voc_df = spark.createDataFrame([(t,) for t in vocab], "token string")
    # Token trong tu dien (minDF=2) -> dung cho Jaccard / diversity cung tap voi MinHash
    toks = (df.select("food_id", F.explode("tokens").alias("token")).join(F.broadcast(voc_df), "token")
            .groupBy("food_id").agg(F.array_sort(F.collect_list("token")).alias("tokens")))
    R.save(toks, P, "item_tokens", coalesce=1)
    toks = R.load(spark, P, "item_tokens").cache()
    report["items"] = n_items
    report["vocab_size"] = len(vocab)
    report["vocab_by_kind"] = {k: sum(1 for t in vocab if (t.startswith(k) if k != "âm tiết" else
                                                          not any(t.startswith(p) for p in ("nl:", "cat=", "protein=", "method=", "type=", "season=", "tag="))))
                               for k in ("âm tiết", "nl:", "cat=", "protein=", "method=", "type=", "season=", "tag=")}
    report["tokens_per_item_avg"] = round(toks.select(F.avg(F.size("tokens"))).first()[0], 2)
    report["items_without_tokens"] = n_items - toks.count()

# ===========================================================================
# 2. TF-IDF DANG DAI + DO TUONG TU CHINH XAC (chi muc nguoc)
# ===========================================================================
with T("exact_similarity"):
    t0 = time.time()
    long = toks.select("food_id", F.explode("tokens").alias("token"))
    dfq = long.groupBy("token").agg(F.count("*").alias("df"))
    w = (long.join(dfq, "token")
         .withColumn("idf", F.log((F.lit(n_items) + 1) / (F.col("df") + 1)))
         .withColumn("w", F.col("idf") / F.sqrt(F.sum(F.col("idf") ** 2).over(Window.partitionBy("food_id"))))
         .select("food_id", "token", "w").cache())
    n_terms = w.count()
    report["pairs_before_groupby"] = dfq.select(F.sum(F.col("df") * (F.col("df") - 1) / 2)).first()[0]
    a, b = w.alias("a"), w.alias("b")
    pairs = (a.join(b, (F.col("a.token") == F.col("b.token")) & (F.col("a.food_id") < F.col("b.food_id")))
             .groupBy(F.col("a.food_id").alias("i"), F.col("b.food_id").alias("j"))
             .agg(F.sum(F.col("a.w") * F.col("b.w")).alias("cos"), F.count("*").alias("inter")))
    size = toks.select("food_id", F.size("tokens").alias("n"))
    pairs = (pairs.join(size.withColumnRenamed("food_id", "i").withColumnRenamed("n", "ni"), "i")
             .join(size.withColumnRenamed("food_id", "j").withColumnRenamed("n", "nj"), "j")
             .withColumn("jac", F.col("inter") / (F.col("ni") + F.col("nj") - F.col("inter"))))
    both = (pairs.select(F.col("i").alias("food_id"), F.col("j").alias("sim_food_id"), "cos", "jac")
            .unionByName(pairs.select(F.col("j").alias("food_id"), F.col("i").alias("sim_food_id"), "cos", "jac"))
            .persist())
    report["pairs_nonzero"] = both.count() // 2
    sim = (R.top_n(both.withColumnRenamed("sim_food_id", "_s").withColumnRenamed("food_id", "user_id")
                   .select("user_id", F.col("_s").alias("food_id"), F.col("cos").alias("score"), "jac"), N_SIM)
           .select(F.col("user_id").alias("food_id"), F.col("food_id").alias("sim_food_id"),
                   F.col("score").alias("sim"), F.col("jac").alias("jaccard"), "rank"))
    R.save(sim, P, "item_sim", coalesce=4)
    exact_jac20 = (R.top_n(both.select(F.col("food_id").alias("user_id"), F.col("sim_food_id").alias("food_id"),
                                       F.col("jac").alias("score")), 20)
                   .select(F.col("user_id").alias("i"), F.col("food_id").alias("j")).cache())
    n_exact = exact_jac20.count()
    report["exact_seconds"] = round(time.time() - t0, 1)
    both.unpersist()

    # Doi chieu trong so SQL voi pipeline CountVectorizer -> IDF -> Normalizer tren 30 mon
    sample = vec.orderBy(F.xxhash64("food_id", F.lit(R.SEED))).limit(30).collect()
    wd = {(r["food_id"], r["token"]): r["w"] for r in
          w.join(spark.createDataFrame([(r["food_id"],) for r in sample], "food_id int"), "food_id").collect()}
    md = 0.0
    for r in sample:
        v = r["vec"]
        for idx, val in zip(v.indices, v.values):
            md = max(md, abs(val - wd.get((r["food_id"], vocab[idx]), 0.0)))
    report["check_tfidf_sql_vs_pipeline_max_abs_diff"] = md

# ===========================================================================
# 3. MinHashLSH (xap xi Jaccard) - recall@20 va thoi gian so voi cach tinh chinh xac
# ===========================================================================
with T("minhash"):
    mh_in = vec.filter(F.size(F.col("tokens")) > 0).select("food_id", "tf")
    report["minhash"] = []
    for nh in ((3,) if args.quick else (3, 5, 10)):
        t0 = time.time()
        mh = MinHashLSH(inputCol="tf", outputCol="hashes", numHashTables=nh, seed=R.SEED).fit(mh_in)
        cand = (mh.approxSimilarityJoin(mh_in, mh_in, 0.9, distCol="dist")
                .select(F.col("datasetA.food_id").alias("user_id"), F.col("datasetB.food_id").alias("food_id"),
                        (-F.col("dist")).alias("score"))
                .filter(F.col("user_id") != F.col("food_id")).persist())
        n_cand = cand.count()
        top = R.top_n(cand, 20).select(F.col("user_id").alias("i"), F.col("food_id").alias("j"))
        hit = top.join(exact_jac20, ["i", "j"]).count()
        report["minhash"].append({"numHashTables": nh, "candidate_pairs": n_cand, "recall@20": round(hit / n_exact, 4),
                                  "seconds": round(time.time() - t0, 1)})
        print(f"[06] minhash {report['minhash'][-1]}", flush=True)
        cand.unpersist()

# Vi du mon tuong tu (de doc kiem tra bang mat)
sim = R.load(spark, P, "item_sim").cache()
names = vec.select("food_id", "dish_name")
ex = {}
for q in ("Canh chua cá lóc", "Thịt kho trứng", "Gỏi cuốn tôm thịt", "Chè đậu xanh"):
    hit_ids = [r["food_id"] for r in names.filter(F.lower("dish_name").contains(q.lower())).limit(1).collect()]
    if hit_ids:
        rows = (sim.filter((F.col("food_id") == hit_ids[0]) & (F.col("rank") <= 5))
                .join(names.withColumnRenamed("food_id", "sim_food_id"), "sim_food_id").orderBy("rank").collect())
        ex[q] = [f"{r['dish_name']} ({r['sim']:.2f})" for r in rows]
report["examples_top5_similar"] = ex

# ===========================================================================
# 4. GOI Y CHO USER + DANH GIA (cung tap user voi 06b)
# ===========================================================================
for v in ("val", "test"):
    with T(f"{v}:recs"):
        truth = R.load(spark, P, "truth", v)
        ug = R.load(spark, P, "user_groups", v)
        target = truth.select("user_id") if v == "val" else ug.filter("n_events > 0").select("user_id")
        hist = (R.load(spark, P, "implicit", v).join(target, "user_id")
                .select("user_id", "food_id", R.conf_expr().alias("conf")))
        hist = R.top_n(hist.withColumnRenamed("conf", "score"), N_HIST).select("user_id", F.col("food_id").alias("src"),
                                                                            F.col("score").alias("conf"))
        sc = (hist.join(F.broadcast(sim.select(F.col("food_id").alias("src"), F.col("sim_food_id").alias("food_id"), "sim")),
                        "src")
              .withColumn("c", F.col("conf") * F.col("sim"))
              .groupBy("user_id", "food_id")
              .agg(F.sum("c").alias("score"), F.max_by("src", "c").alias("because_food_id")))
        recs = R.top_n(sc, N_REC).select("user_id", "food_id", "rank", "score", "because_food_id")
        R.save(recs, P, "recs_content", v)
        pu = R.per_user_metrics(R.load(spark, P, "recs_content", v), truth)
        R.save(pu, P, "eval_content", v)
        report[v] = {"ranking": R.summarize(R.load(spark, P, "eval_content", v)),
                     "users_with_recs": R.load(spark, P, "recs_content", v).select("user_id").distinct().count()}
        print(f"[06] {v} content ndcg@10 = {report[v]['ranking'][0]['ndcg@10']}", flush=True)

report["timings_s"] = T.parts
report["total_seconds"] = T.total()
R.write_report(P, "content", report)
spark.stop()
