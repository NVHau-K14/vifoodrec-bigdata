"""
07_export_mongo.py - Xuat ket qua tren HDFS sang MongoDB (tang phuc vu cho API va dashboard, D14).

MongoDB chi chua ket qua da tinh xong. Su kien tho va bang trung gian buoc 06 van chi nam tren HDFS.
Moc thoi gian cua dashboard: 01/09/2026 (recs_final, history, profile deu dung lich su den het 08/2026).

Collection (_id la khoa nghiep vu):
  dishes            foods + dish_features + dish_stats (stats, ca nam mo phong) + companion; name_search khong dau
  recs              1 doc / user: items = 50 mon (rank, food_id, score, source, because_food_id) tu recs_final
  similar           1 doc / mon: items = 50 mon tuong tu (item_sim)
  users             ho so + group + cluster_k3/k8/k11 + profile + history (10 mon nau nhieu nhat)
                    + test_cooks (mon nau thang 09/2026) + truth (persona, CHI de kiem chung)
  popular           top 100 cua pop_test (chung, 2 thang cuoi, vung-tuoi)
  clusters          cluster_profile (k = 3, 8, 11)
  meal_rules, ingredient_rules, ingredient_edges      luat FP-Growth (06d)
  analysis_<bang>   13 bang cua buoc 05 (tru dish_stats, da gop vao dishes)
  metrics           bang do do cua 06f (cot JSON tach thanh document con)
  reports           cac file data/output/*report*.json va models_metrics.json
  overview          so lieu trang Tong quan: so mon, user, su kien theo loai, dung luong HDFS
  trending          de trong, chi tao index (phan Structured Streaming ghi vao sau)

Cach ghi (D14):
  - recs, users: foreachPartition tren executor, pymongo insert_many theo lo 1.000 doc (ordered=False).
    BulkWriteError chi bo qua khi MOI loi deu la trung khoa 11000 (Spark chay lai task); loi khac -> dung job.
  - bang nho: collect() ve driver roi insert_many.
  - moi collection ghi vao <ten>__staging, kiem tra so doc, tao index, roi renameCollection(dropTarget=True):
    API khong bao gio thay collection ghi do, chay lai ra cung ket qua.
  - date -> chuoi "yyyy-MM-dd", timestamp -> chuoi theo mui gio phien Spark (Asia/Ho_Chi_Minh, get_spark()),
    DecimalType -> double, NaN -> null.

Dau vao : HDFS /data/curated/foods, /data/features/dish_features, /data/events/{users,users_truth,events},
          /data/results/analysis/*, /data/results/models/{recs_final,item_sim,companion,rules_*,ingredient_edges,
          user_clusters,cluster_profile,metrics,pop_test,user_features_test,user_groups_test,truth_test}
          data/output/*report*.json, models_metrics.json
Dau ra  : MongoDB database MONGO_DB (mac dinh vifood; --local -> vifood_local)
          data/output/export_report.json (so doc, kiem tra, collStats, explain(), thoi gian ghi)

Chay tren cum:  python src/07_export_mongo.py                 (--only dishes,recs : chi xuat mot so collection)
Chay thu local: python src/07_export_mongo.py --local         (doc data/hdfs_local, ghi database vifood_local)
"""
import argparse
import datetime
import decimal
import glob
import json
import math
import os
import sys
import time

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pyspark.sql import Window, functions as F, types as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, get_spark  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--local", action="store_true", help="chay Spark local tren data/hdfs_local, ghi database vifood_local")
ap.add_argument("--only", default="", help="chi xuat cac collection nay, cach nhau dau phay (vd dishes,recs)")
ap.add_argument("--db", default=None, help="ten database (mac dinh MONGO_DB, hoac vifood_local khi --local)")
args = ap.parse_args()

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = args.db or ("vifood_local" if args.local else os.getenv("MONGO_DB", "vifood"))
ONLY = {x.strip() for x in args.only.split(",") if x.strip()}
HIST_MAX = "2026-08"        # view test: lich su den het 08/2026 (giong recs_final, D12)
N_HISTORY = 10
N_PARTS = 8
BATCH = 1000

spark = get_spark("07_export_mongo", local=args.local)
P = Paths(local=args.local)
M, A = f"{P.results}/models", f"{P.results}/analysis"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
report = {"mode": "local" if args.local else "cluster", "db": DB_NAME,
          "spark_session_timezone": spark.conf.get("spark.sql.session.timeZone"),
          "collections": {}, "checks": {}, "explain": {}, "timings_s": {}}
T0 = time.time()


def log(msg):
    print(f"[07] {msg}", flush=True)


def want(name):
    return not ONLY or name in ONLY or (name.startswith("analysis_") and "analysis" in ONLY)


def read_or_local(path, local_file):
    try:
        return spark.read.parquet(path)
    except Exception:
        if not args.local:
            raise
        return spark.read.parquet("file://" + os.path.join(P.processed_local, local_file))


# ---------------------------------------------------------------------------
# Chuyen kieu Spark -> BSON
# ---------------------------------------------------------------------------
def fix_types(df):
    """Cot cap 1: DecimalType -> double, date -> chuoi yyyy-MM-dd. Timestamp phai doi truoc bang date_format."""
    for f in df.schema.fields:
        if isinstance(f.dataType, T.DecimalType):
            df = df.withColumn(f.name, F.col(f.name).cast("double"))
        elif isinstance(f.dataType, T.DateType):
            df = df.withColumn(f.name, F.date_format(f.name, "yyyy-MM-dd"))
        elif isinstance(f.dataType, T.TimestampType):
            raise TypeError(f"cot {f.name} la timestamp: doi sang chuoi bang date_format truoc khi xuat")
    return df


def clean(v):
    """Kiem tra lai o Python: NaN -> None, Decimal -> float, date -> chuoi (phong khi kieu long ben trong struct)."""
    if isinstance(v, float):
        return None if math.isnan(v) else v
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v


def to_doc(row):
    return clean(row.asDict(recursive=True))


def safe_keys(o):
    """Ten truong co dau cham (vd "4.0" trong report) -> dau phay; '$' o dau -> '_'. '@' giu nguyen (D14)."""
    if isinstance(o, dict):
        return {(("_" + k[1:]) if k.startswith("$") else k).replace(".", ","): safe_keys(v) for k, v in o.items()}
    if isinstance(o, list):
        return [safe_keys(x) for x in o]
    if isinstance(o, float) and math.isnan(o):
        return None
    return o


def insert_docs(coll, docs):
    """insert_many theo lo; BulkWriteError chi bo qua khi MOI loi la trung khoa 11000 (D14 c). Tra ve so doc trung."""
    from pymongo.errors import BulkWriteError
    dup = 0
    for i in range(0, len(docs), BATCH):
        try:
            coll.insert_many(docs[i:i + BATCH], ordered=False)
        except BulkWriteError as e:
            errs = e.details.get("writeErrors", [])
            if not errs or e.details.get("writeConcernErrors") or any(x.get("code") != 11000 for x in errs):
                raise
            dup += len(errs)
    return dup


def make_partition_writer(uri, db_name, coll_name, transform=None):
    """Ham chay tren executor: moi partition 1 MongoClient, ghi theo lo 1.000 doc. transform(doc) sua doc truoc khi ghi."""
    def write(rows):
        from pymongo import MongoClient as MC
        c = MC(uri)
        coll = c[db_name][coll_name]
        buf, dup = [], 0
        for r in rows:
            d = to_doc(r)
            buf.append(transform(d) if transform else d)
            if len(buf) >= BATCH:
                dup += insert_docs(coll, buf)
                buf = []
        if buf:
            dup += insert_docs(coll, buf)
        c.close()
        if dup:
            print(f"[07] partition bo qua {dup} doc trung khoa (task chay lai)", flush=True)
    return write


def coll_stats(name):
    s = next(db[name].aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
    return {"count": s["count"], "size_bytes": s["size"], "avg_obj_bytes": s.get("avgObjSize", 0),
            "storage_bytes": s["storageSize"], "total_index_bytes": s["totalIndexSize"], "n_indexes": s["nindexes"],
            "compression_ratio": round(s["size"] / s["storageSize"], 2) if s["storageSize"] else None}


def export(name, df=None, docs=None, indexes=(), big=False, transform=None):
    """Ghi vao <name>__staging -> kiem tra so doc -> tao index -> doi ten (nguyen tu). Ghi so lieu vao report."""
    if not want(name):
        return
    t = time.time()
    stg = f"{name}__staging"
    db.drop_collection(stg)
    db.create_collection(stg)
    if big:
        df = fix_types(df)
        expected = df.count()
        df.repartition(N_PARTS).foreachPartition(make_partition_writer(MONGO_URI, DB_NAME, stg, transform))
    else:
        if docs is None:
            docs = [to_doc(r) for r in fix_types(df).collect()]
        expected = len(docs)
        if docs:
            insert_docs(db[stg], docs)
    t_write = time.time() - t
    got = db[stg].count_documents({})
    if got != expected:
        raise RuntimeError(f"{name}: MongoDB co {got} doc, Spark/nguon co {expected}")
    names = []
    for keys, opts in indexes:
        names.append(db[stg].create_index(keys, **opts))
    db[stg].rename(name, dropTarget=True)
    info = {"docs": got, "expected": expected, "write_s": round(t_write, 1), "total_s": round(time.time() - t, 1),
            "method": f"foreachPartition ({N_PARTS} partition)" if big else "collect + insert_many",
            "indexes": ["_id_"] + names}
    report["collections"][name] = info
    log(f"{name}: {got} doc, ghi {info['write_s']}s, tong {info['total_s']}s")


def idx(keys, **opts):
    return (keys, opts)


# ===========================================================================
# 1. NGUON CHUNG
# ===========================================================================
foods = read_or_local(f"{P.curated}/foods", "foods_v2.parquet")
feat = spark.read.parquet(f"{P.features}/dish_features")
dstats = spark.read.parquet(f"{A}/dish_stats")
recs_final = spark.read.parquet(f"{M}/recs_final")
item_sim = spark.read.parquet(f"{M}/item_sim")
companion = spark.read.parquet(f"{M}/companion")
food_ids = foods.select("food_id").cache()
report["source_rows"] = {"foods": food_ids.count(), "recs_final": recs_final.count(), "item_sim": item_sim.count(),
                         "companion": companion.count()}

# Ten khong dau: chu thuong + translate() (ham Spark co san, khong UDF). 'đ' khong phai dau to hop -> phai map rieng
VN_FROM = ("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")
VN_TO = ("aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd")
assert len(VN_FROM) == len(VN_TO)
name_search = F.trim(F.regexp_replace(F.translate(F.lower("dish_name"), VN_FROM, VN_TO), r"[^a-z0-9]+", " "))

# ===========================================================================
# 2. DISHES
# ===========================================================================
with_comp = (companion.groupBy("food_id")
             .agg(F.sort_array(F.collect_list(F.struct("rank", F.col("companion_id").alias("food_id"),
                                                      "confidence", "lift"))).alias("companions")))
comp_type = with_comp.schema["companions"].dataType
# dish_type goc khong dang tin (dung dish_type_fixed), cooking_time la so ngau nhien
dishes = (foods.drop("dish_type", "cooking_time", "source_stt", "in_original_clean", "dup_name_group")
          .withColumn("nutrition", F.struct("calories", "fat", "fiber", "sugar", "protein"))
          .drop("calories", "fat", "fiber", "sugar", "protein")
          .withColumn("name_search", name_search)
          .join(feat.drop("dish_name", "source"), "food_id")
          .join(dstats.select("food_id", F.struct("views", "favorites", "cooks", "rates", "avg_rating",
                                                  "cook_rank").alias("stats")), "food_id", "left")
          .join(with_comp, "food_id", "left")
          .withColumn("companions", F.coalesce("companions", F.array().cast(comp_type)))
          .withColumnRenamed("food_id", "_id")
          .orderBy("_id"))
export("dishes", dishes, indexes=[
    idx([("name_search", TEXT), ("dish_name", TEXT)], default_language="none", name="text_ten_mon"),
    idx([("name_search", ASCENDING)]),
    idx([("is_vegetarian", ASCENDING), ("stats.cook_rank", ASCENDING)]),
    idx([("is_quick", ASCENDING), ("stats.cook_rank", ASCENDING)]),
    idx([("meal_types", ASCENDING), ("stats.cook_rank", ASCENDING)]),
    idx([("dish_category", ASCENDING), ("stats.cook_rank", ASCENDING)]),
    idx([("stats.cook_rank", ASCENDING)]),
])

# ===========================================================================
# 3. RECS, SIMILAR
# ===========================================================================
# because_cooked (D15): chi phan tu content_slot co truong nay. 06f da ghi vao cau ly do
# ("Giong mon X ban da nau" / "... ban da xem"), bang recs_final khong giu co because_is_cooked
recs = (recs_final
        .withColumn("because_cooked", F.when(F.col("source") == "content_slot",
                                             F.col("reason").endswith(" bạn đã nấu")))
        .groupBy("user_id")
        .agg(F.sort_array(F.collect_list(F.struct(F.col("rank").cast("int").alias("rank"), "food_id", "score",
                                                  "source", "because_food_id", "because_cooked"))).alias("items"))
        .withColumnRenamed("user_id", "_id"))


def drop_null_because_cooked(doc):
    for it in doc["items"]:
        if it.get("because_cooked") is None:
            it.pop("because_cooked", None)
    return doc


export("recs", recs, big=True, transform=drop_null_because_cooked)

similar = (item_sim.groupBy("food_id")
           .agg(F.sort_array(F.collect_list(F.struct("rank", F.col("sim_food_id").alias("food_id"),
                                                     "sim", "jaccard"))).alias("items"))
           .withColumnRenamed("food_id", "_id").orderBy("_id"))
export("similar", similar)

# ===========================================================================
# 4. USERS
# ===========================================================================
# Lich su nau den het 08/2026, tinh tu su kien cook (last_ts cua implicit_test la su kien cuoi MOI loai)
cooks_hist = (spark.read.parquet(f"{P.events}/events")
              .where((F.col("month") <= HIST_MAX) & (F.col("event_type") == "cook"))
              .groupBy("user_id", "food_id")
              .agg(F.count("*").alias("n_cook"), F.max("ts").alias("last_ts")))
w_hist = Window.partitionBy("user_id").orderBy(F.desc("n_cook"), F.desc("last_ts"), F.asc("food_id"))
history = (cooks_hist.withColumn("r", F.row_number().over(w_hist)).where(F.col("r") <= N_HISTORY)
           .groupBy("user_id")
           .agg(F.sort_array(F.collect_list(F.struct(
               "r", "food_id", "n_cook",
               F.date_format("last_ts", "yyyy-MM-dd HH:mm").alias("last_cook")))).alias("h"))
           .select("user_id", F.transform("h", lambda x: x.dropFields("r")).alias("history")))
hist_type = history.schema["history"].dataType

ufeat = spark.read.parquet(f"{M}/user_features_test")
profile_cols = ["n_events", "n_cook", "n_rate", "avg_rating", "share_chay", "share_haisan", "share_ngot",
                "share_nhanh", "share_cay", "pref_slot"]
truth_test = spark.read.parquet(f"{M}/truth_test").select("user_id", F.array_sort("items").alias("test_cooks"))
utruth = spark.read.parquet(f"{P.events}/users_truth")
users = (spark.read.parquet(f"{P.events}/users")
         .join(spark.read.parquet(f"{M}/user_groups_test").select("user_id", "group"), "user_id", "left")
         .join(spark.read.parquet(f"{M}/user_clusters"), "user_id", "left")
         .join(ufeat.select("user_id", F.struct(*profile_cols).alias("profile")), "user_id", "left")
         .join(history, "user_id", "left")
         .withColumn("history", F.coalesce("history", F.array().cast(hist_type)))
         .join(truth_test, "user_id", "left")
         # truth: CHI de kiem chung, endpoint goi y cua buoc 08 khong duoc tra truong nay (D14)
         .join(utruth.select("user_id", F.struct("persona_main", "persona_sub").alias("truth")), "user_id", "left")
         .withColumnRenamed("user_id", "_id"))
export("users", users, big=True, indexes=[
    idx([("cluster_k8", ASCENDING)]),
    idx([("region", ASCENDING), ("age_group", ASCENDING)]),
    idx([("truth.persona_main", ASCENDING)]),
])

# ===========================================================================
# 5. BANG NHO CUA BUOC 06
# ===========================================================================
pop = spark.read.parquet(f"{M}/pop_test")
pop_docs = []
for r in (pop.groupBy("kind", "region", "age_group")
          .agg(F.sort_array(F.collect_list(F.struct("rank", "food_id", "cooks"))).alias("items"))
          .orderBy("kind", "region", "age_group").collect()):
    key = r["kind"] if r["region"] is None else f"{r['kind']}|{r['region']}|{r['age_group']}"
    pop_docs.append(clean({"_id": key, "kind": r["kind"], "region": r["region"], "age_group": r["age_group"],
                           "items": [x.asDict() for x in r["items"]]}))
export("popular", docs=pop_docs)

prof = spark.read.parquet(f"{M}/cluster_profile")
feat_cols = [c for c in prof.columns if c not in ("k", "cluster", "n_users", "persona_pho_bien_kiem_chung",
                                                  "persona_share")]
clusters = (prof.select(F.concat(F.lit("k"), "k", F.lit("_c"), "cluster").alias("_id"), "k", "cluster", "n_users",
                        F.struct(*feat_cols).alias("features"),
                        F.col("persona_pho_bien_kiem_chung").alias("persona_kiem_chung"), "persona_share")
            .orderBy("k", "cluster"))
export("clusters", clusters, indexes=[idx([("k", ASCENDING), ("cluster", ASCENDING)])])

export("meal_rules", spark.read.parquet(f"{M}/rules_meal").orderBy(F.desc("lift"), "antecedent", "consequent"),
       indexes=[idx([("antecedent", ASCENDING)]), idx([("consequent", ASCENDING)])])
export("ingredient_rules", spark.read.parquet(f"{M}/rules_ingredients")
       .orderBy("variant", F.desc("lift"), "antecedent", "consequent"),
       indexes=[idx([("variant", ASCENDING), ("lift", DESCENDING)])])
export("ingredient_edges", spark.read.parquet(f"{M}/ingredient_edges").orderBy("variant", F.desc("lift"), "src", "dst"),
       indexes=[idx([("variant", ASCENDING), ("lift", DESCENDING)])])

met_docs = []
for r in spark.read.parquet(f"{M}/metrics").orderBy("view", "variant", "model", "group").collect():
    d = r.asDict()
    m = json.loads(d["metrics"]) if d["metrics"] else {}
    d["metrics"] = {k: v for k, v in m.items() if k not in ("view", "model", "variant", "group")}
    met_docs.append(clean(safe_keys(d)))
export("metrics", docs=met_docs, indexes=[idx([("view", ASCENDING), ("variant", ASCENDING), ("model", ASCENDING)])])

# ===========================================================================
# 6. KET QUA PHAN TICH BUOC 05
# ===========================================================================
ANALYSIS_IDX = {
    "lift_by_group": [idx([("group_type", ASCENDING), ("group_value", ASCENDING)])],
    "top_dish_by_slot": [idx([("meal_slot", ASCENDING), ("rk", ASCENDING)])],
    "trend_month_category": [idx([("month", ASCENDING)])],
    "season_month": [idx([("region", ASCENDING), ("month", ASCENDING)])],
    "top_ingredients": [idx([("cook_rank", ASCENDING)])],
}
# 13 bang cua buoc 05; dish_stats da gop vao dishes.stats
ANALYSIS_TABLES = ["heatmap_hour_dow", "trend_month_category", "season_month", "top_dish_by_slot", "lift_by_group",
                   "funnel_by_category", "catalog_vs_cooked", "top_ingredients", "rating_dist", "session_size",
                   "repeat_by_category", "user_activity", "long_tail_curve"]
for tbl in ANALYSIS_TABLES:
    df = spark.read.parquet(f"{A}/{tbl}")
    export(f"analysis_{tbl}", df.orderBy(*df.columns), indexes=ANALYSIS_IDX.get(tbl, []))

# ===========================================================================
# 7. REPORTS, OVERVIEW, TRENDING
# ===========================================================================
rep_files = sorted(glob.glob(os.path.join(P.output_local, "*report*.json")) +
                   [os.path.join(P.output_local, "models_metrics.json")])
rep_docs = []
for fpath in rep_files:
    name = os.path.splitext(os.path.basename(fpath))[0]
    if name == "export_report":
        continue
    with open(fpath, encoding="utf-8") as fh:
        rep_docs.append({"_id": name, "file": os.path.basename(fpath), "content": safe_keys(json.load(fh))})
export("reports", docs=rep_docs)

if want("overview"):
    jvm = spark._jvm
    fs_conf = spark._jsc.hadoopConfiguration()
    root = P.results.rsplit("/", 1)[0]          # .../data
    hdfs = {}
    for sub in ["raw", "curated", "features", "events", "results", "models"]:
        p = jvm.org.apache.hadoop.fs.Path(f"{root}/{sub}")
        fs = p.getFileSystem(fs_conf)
        if fs.exists(p):
            cs = fs.getContentSummary(p)
            hdfs[sub] = {"bytes": cs.getLength(), "bytes_with_replicas": cs.getSpaceConsumed(),
                         "files": cs.getFileCount()}
    ev = spark.read.parquet(f"{P.events}/events")
    ev_by_type = {r["event_type"]: r["count"] for r in ev.groupBy("event_type").count().collect()}
    overview = {
        "_id": "overview",
        "exported_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(timespec="seconds"),
        "mode": report["mode"],
        "n_dishes": report["source_rows"]["foods"],
        "n_users": spark.read.parquet(f"{P.events}/users").count(),
        "n_events": sum(ev_by_type.values()),
        "events_by_type": ev_by_type,
        "event_months": [r["month"] for r in ev.select("month").distinct().orderBy("month").collect()],
        "n_recs_rows": report["source_rows"]["recs_final"],
        "hdfs": hdfs,
        "reference_date": "2026-09-01",
        "notes": [
            "Dữ liệu hành vi (sự kiện, user, persona) là MÔ PHỎNG; danh mục món là món thật (Cooky, Món Ngon Mỗi Ngày).",
            "dishes.stats là thống kê cả năm mô phỏng (10/2025–09/2026, gồm cả tháng val và test), chỉ để mô tả, "
            "không phải dữ liệu mô hình đã thấy.",
            "Gợi ý (recs), users.history và users.profile dùng lịch sử đến hết 08/2026; mốc của dashboard là 01/09/2026.",
            "dishes.nutrition là số ngẫu nhiên của dữ liệu gốc: lưu lại nhưng không hiển thị.",
            "users.truth (persona thật) chỉ để kiểm chứng phân cụm; endpoint gợi ý không trả trường này.",
        ],
    }
    report["overview"] = {k: v for k, v in overview.items() if k != "_id"}
    export("overview", docs=[overview])

if want("trending"):
    db["trending"].create_index([("window_end", DESCENDING)])
    report["collections"]["trending"] = {"docs": db["trending"].count_documents({}),
                                        "note": "chỉ tạo index, phần Structured Streaming ghi vào sau"}

# ===========================================================================
# 8. KIEM TRA
# ===========================================================================
t = time.time()
C = report["checks"]

# Mui gio (D14 a): buoc 04 chon GIO BAT DAU phien trong khung [h0, h1) cua meal_slot (cac su kien sau trong phien
# co the lan sang gio ke tiep). Doc theo mui gio phien, gio bat dau cua moi phien phai nam trong khung; lech 7 tieng
# thi gan nhu moi phien deu sai.
SLOT_HOURS = {"sáng": (6, 9), "trưa": (10, 13), "tối": (16, 20), "khuya": (21, 24)}
sess = (spark.read.parquet(f"{P.events}/events").groupBy("session_id", "meal_slot")
        .agg(F.hour(F.min("ts")).alias("h")))
slot_ok = F.lit(False)
for s, (h0, h1) in SLOT_HOURS.items():
    slot_ok = slot_ok | ((F.col("meal_slot") == s) & (F.col("h") >= h0) & (F.col("h") < h1))
tz = sess.agg(F.count("*").alias("n"), F.sum((~slot_ok).cast("int")).alias("bad")).first()
C["timezone_session_start_outside_meal_slot"] = {"sessions": tz["n"], "outside": tz["bad"]}

# Toan ven tham chieu: moi food_id duoc nhac den deu co trong dishes
refs = (recs_final.select("food_id")
        .union(recs_final.where(F.col("because_food_id").isNotNull()).select(F.col("because_food_id").alias("food_id")))
        .union(item_sim.select(F.col("sim_food_id").alias("food_id")))
        .union(companion.select(F.col("companion_id").alias("food_id")))
        .union(pop.select("food_id"))
        .union(cooks_hist.select("food_id"))
        .union(truth_test.select(F.explode("test_cooks").alias("food_id")))
        .distinct())
C["food_id_not_in_dishes"] = refs.join(food_ids, "food_id", "left_anti").count()

if want("recs"):
    agg = list(db["recs"].aggregate([{"$project": {"n": {"$size": "$items"}}},
                                     {"$group": {"_id": None, "docs": {"$sum": 1}, "items": {"$sum": "$n"},
                                                 "min": {"$min": "$n"}, "max": {"$max": "$n"}}}]))[0]
    C["recs_items"] = {"docs": agg["docs"], "items_total": agg["items"], "items_min": agg["min"],
                       "items_max": agg["max"], "hdfs_rows": report["source_rows"]["recs_final"],
                       "ok": agg["items"] == report["source_rows"]["recs_final"]}
    # 5 user mau theo hash (4 user bat ky + 1 user lanh): danh sach tren MongoDB phai giong het recs_final
    ug = spark.read.parquet(f"{M}/user_groups_test").withColumn("h", F.xxhash64("user_id"))
    sample = ([r["user_id"] for r in ug.orderBy("h").limit(4).collect()] +
              [r["user_id"] for r in ug.where(F.col("group") == "lạnh").orderBy("h").limit(1).collect()])
    hdfs_rows = (recs_final.where(F.col("user_id").isin(sample))
                 .select("user_id", F.col("rank").cast("int").alias("rank"), "food_id", "score", "source",
                         "because_food_id").collect())
    sample_res = []
    for u in sample:
        h = sorted([(r["rank"], r["food_id"], r["score"], r["source"], r["because_food_id"])
                    for r in hdfs_rows if r["user_id"] == u])
        doc = db["recs"].find_one({"_id": u})
        m = [(x["rank"], x["food_id"], x["score"], x["source"], x["because_food_id"]) for x in doc["items"]]
        grp = ug.where(F.col("user_id") == u).first()["group"]
        sample_res.append({"user_id": u, "group": grp, "n_items": len(m), "identical": m == h})
    C["recs_sample_users"] = sample_res
    # because_cooked (D15): chi co o content_slot; ty le true phai bang content_slot_because_cooked_pct cua 06f
    bc = list(db["recs"].aggregate([{"$unwind": "$items"},
                                    {"$group": {"_id": {"source": "$items.source",
                                                        "has": {"$ne": [{"$type": "$items.because_cooked"}, "missing"]},
                                                        "val": "$items.because_cooked"}, "n": {"$sum": 1}}}]))
    # $group bo khoa "val" khi truong khong ton tai -> dien None
    C["recs_because_cooked"] = sorted([{"source": x["_id"]["source"], "has": x["_id"]["has"],
                                        "val": x["_id"].get("val"), "n": x["n"]} for x in bc],
                                      key=lambda x: (x["source"], str(x["val"])))

if want("similar"):
    agg = list(db["similar"].aggregate([{"$project": {"n": {"$size": "$items"}}},
                                        {"$group": {"_id": None, "items": {"$sum": "$n"}, "min": {"$min": "$n"},
                                                    "max": {"$max": "$n"}}}]))[0]
    C["similar_items"] = {"items_total": agg["items"], "min": agg["min"], "max": agg["max"],
                          "hdfs_rows": report["source_rows"]["item_sim"]}

if want("users"):
    C["users"] = {
        "with_history": db["users"].count_documents({"history.0": {"$exists": True}}),
        "with_test_cooks": db["users"].count_documents({"test_cooks": {"$ne": None}}),
        "with_cluster_k8": db["users"].count_documents({"cluster_k8": {"$ne": None}}),
        "with_profile": db["users"].count_documents({"profile": {"$ne": None}}),
        "with_truth": db["users"].count_documents({"truth": {"$ne": None}}),
    }
    C["users"]["history_items"] = history.select(F.explode("history")).count()
    # vi du co 2 mon cung n_cook de thay thu tu theo last_cook
    ex = db["users"].find_one({"history.2": {"$exists": True},
                               "$expr": {"$eq": [{"$arrayElemAt": ["$history.n_cook", 1]},
                                                 {"$arrayElemAt": ["$history.n_cook", 2]}]}}, {"history": 1})
    C["users"]["history_example"] = ex["history"][:5] if ex else None

if want("dishes"):
    C["dishes"] = {"with_companions": db["dishes"].count_documents({"companions.0": {"$exists": True}}),
                   "without_image": db["dishes"].count_documents({"image_link": None}),
                   "name_search_example": db["dishes"].find_one({}, {"dish_name": 1, "name_search": 1})}
report["timings_s"]["checks"] = round(time.time() - t, 1)


# ===========================================================================
# 9. EXPLAIN CAC TRUY VAN TIEU BIEU CUA API (buoc 08)
# ===========================================================================
def plan_stages(p):
    out = []
    while p:
        out.append(p.get("stage") + (f"({p['indexName']})" if p.get("indexName") else ""))
        p = p.get("inputStage") or (p.get("inputStages") or [None])[0]
    return out


def explain(cursor):
    e = cursor.explain()
    ex = e.get("executionStats", {})
    return {"winning_plan": plan_stages(e["queryPlanner"]["winningPlan"]),
            "n_returned": ex.get("nReturned"), "keys_examined": ex.get("totalKeysExamined"),
            "docs_examined": ex.get("totalDocsExamined"), "time_ms": ex.get("executionTimeMillis")}


if want("dishes") and want("recs"):
    uid = C["recs_sample_users"][0]["user_id"] if "recs_sample_users" in C else 1
    rec_ids = [x["food_id"] for x in db["recs"].find_one({"_id": uid})["items"]]
    E = report["explain"]
    E["recs_theo_user"] = {"query": f"recs.find({{_id: {uid}}})", **explain(db["recs"].find({"_id": uid}))}
    # Bu mon (D14 d): cung bo loc, bo mon da co trong danh sach goi y, xep theo stats.cook_rank
    q = {"is_vegetarian": True, "is_quick": True, "meal_types": "tối", "_id": {"$nin": rec_ids}}
    E["bu_mon_theo_bo_loc"] = {"query": "dishes.find({is_vegetarian: true, is_quick: true, meal_types: 'tối', "
                                        "_id: {$nin: <50 món gợi ý>}}).sort({'stats.cook_rank': 1}).limit(10)",
                              **explain(db["dishes"].find(q).sort("stats.cook_rank", ASCENDING).limit(10))}
    E["tim_mon_regex"] = {"query": "dishes.find({name_search: {$regex: 'dau hu'}}).limit(20)",
                          **explain(db["dishes"].find({"name_search": {"$regex": "dau hu"}}).limit(20))}
    E["tim_mon_text_index"] = {"query": "dishes.find({$text: {$search: 'dau hu'}}).limit(20)",
                               **explain(db["dishes"].find({"$text": {"$search": "dau hu"}}).limit(20))}
    E["bu_mon_so_mon_tim_duoc"] = db["dishes"].count_documents(q)

# collStats sau fsync: storageSize chi cap nhat khi WiredTiger checkpoint (ngay sau khi ghi con bang 0)
db.client.admin.command("fsync")
for name, info in report["collections"].items():
    if name != "trending":
        info.update(coll_stats(name))
        log(f"{name}: size {info['size_bytes'] / 1e6:.1f}MB, storage {info['storage_bytes'] / 1e6:.1f}MB, "
            f"index {info['total_index_bytes'] / 1e6:.1f}MB")
report["timings_s"]["total"] = round(time.time() - T0, 1)
out = os.path.join(P.output_local, "export_report.json")
# --only: gop vao report cu cua cung database (giu so lieu cac collection khong chay lai), ghi lai lan chay nay
if ONLY and os.path.exists(out):
    with open(out, encoding="utf-8") as fh:
        old = json.load(fh)
    if old.get("db") == DB_NAME:
        for k in ("collections", "checks", "explain"):
            report[k] = {**old.get(k, {}), **report[k]}
        report["source_rows"] = {**old.get("source_rows", {}), **report["source_rows"]}
        report["partial_runs"] = old.get("partial_runs", []) + [
            {"only": sorted(ONLY), "at": datetime.datetime.now().isoformat(timespec="seconds"),
             "timings_s": report["timings_s"]}]
        report["timings_s"] = old.get("timings_s", report["timings_s"])
with open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
log(f"xong sau {report['timings_s']['total']}s -> {out}")
log(f"kiem tra: mui gio {C['timezone_session_start_outside_meal_slot']}, food_id ngoai dishes "
    f"{C['food_id_not_in_dishes']}")
client.close()
spark.stop()
