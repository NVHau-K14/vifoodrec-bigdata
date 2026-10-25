"""
02_clean.py - Lam sach lai ViFoodRec tu 2 file RAW -> bo du lieu "clean v2".

Vi sao khong dung foods.csv (Clean Dataset) cua tac gia: ban do bi loi trong buoc lam sach
(chen "muong" vao giua tu o ~71% so mon, mat dau thanh, cat con dung 4.000 mon, 4 mon bi
nhan doi...). foods.csv CHI con dung de tra food_id cu (ghep theo image_link + ten mon),
nho do ratings.csv van dung duoc.

Dau vao  (HDFS /data/raw):  food_dataset_cookyweb.csv, food_dataset_mnmnweb.csv,
                             foods.csv (chi lay food_id), ratings.csv
Dau ra   (HDFS /data/curated, Parquet):  foods/ , ratings_original/
         (tren may, de mo xem): data/processed/foods_v2.{parquet,csv},
                                 data/processed/ratings_v2.{parquet,csv}
         bao cao lam sach:       data/output/clean_report.json

Chay tren cum (trong container jupyter):  python src/02_clean.py
Chay thu 1 may (khong can HDFS):           python src/02_clean.py --local
"""
import argparse
import json
import os
import sys

from pyspark.sql import Window, functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (Paths, Timer, clean_text, export_single, fix_word_case, get_spark,  # noqa: E402
                    name_key, nfc_udf, parse_ingredients_udf, read_csv)

NEW_ID_START = 4001          # mon moi (khong co trong foods.csv goc) danh so tu day
TAG_BLACKLIST = ["nghệ thuật nấu ăn ngon gia đình"]   # tag chung chung, khong mo ta mon

ap = argparse.ArgumentParser()
ap.add_argument("--local", action="store_true", help="chay Spark local, doc data/raw tren may")
args = ap.parse_args()

spark = get_spark("02_clean", local=args.local)
P = Paths(local=args.local)
report = {}
T = Timer("02")      # thoi gian tung phan + job group Spark (D17)
T.mark("read_raw")

# ---------------------------------------------------------------------------
# 1. Doc va gop 2 nguon raw ve chung mot luoc do
# ---------------------------------------------------------------------------
ck = read_csv(spark, f"{P.raw}/food_dataset_cookyweb.csv")
mn = read_csv(spark, f"{P.raw}/food_dataset_mnmnweb.csv")
report["raw_rows"] = {"cooky": ck.count(), "mnmn": mn.count()}


def unify(df, source):
    def col(name):  # cot chi co o MNMN -> null voi Cooky
        return F.col(f"`{name}`") if name in df.columns else F.lit(None).cast("string")
    return df.select(
        F.lit(source).alias("source"),
        F.col("STT").cast("int").alias("source_stt"),
        F.col("`Tên món`").alias("name_raw"),
        F.col("`Giới thiệu`").alias("description_raw"),
        F.col("`Loại món`").alias("dish_type_raw"),
        F.col("`Khẩu phần`").alias("serving_raw"),
        F.col("`Time Cooking`").alias("cooking_time_raw"),
        F.col("`Nguyên liệu`").alias("ingredients_raw"),
        col("Sơ chế").alias("preparation_raw"),
        F.col("`Cách làm`").alias("method_raw"),
        col("Cách dùng").alias("serving_tips_raw"),
        col("Mách nhỏ").alias("tips_raw"),
        F.col("Tags").alias("tags_raw"),
        F.col("Calories").alias("calories"), F.col("`Fat Amount`").alias("fat"),
        F.col("`Fiber Amount`").alias("fiber"), F.col("`Sugar Amount`").alias("sugar"),
        F.col("`Protein Amount`").alias("protein"),
        F.col("`Link Ảnh`").alias("image_raw"),
    )


raw = unify(ck, "cooky").unionByName(unify(mn, "mnmn"))

T.mark("clean_dedup_ids")       # buoc 2-5 phan lon la phep bien doi luoi, chay khi ghi
# ---------------------------------------------------------------------------
# 2. Lam sach tung cot
# ---------------------------------------------------------------------------
df = (raw
      # Ten mon: sua tu bi viet hoa loi ("SữA Chua TráI Cây" -> "Sữa Chua Trái Cây"), giu dia danh
      .withColumn("dish_name", fix_word_case(clean_text(F.col("name_raw"))))
      .withColumn("description", clean_text(F.col("description_raw")))
      .withColumn("dish_type", F.trim(nfc_udf(F.col("dish_type_raw"))))
      # Khau phan: "4 người" -> 4 ; "1 'ngườ" -> 1 ; 0 hoac > 50 nguoi -> null (vo ly)
      .withColumn("serving_size", F.regexp_extract("serving_raw", r"(\d+)", 1).try_cast("int"))
      .withColumn("serving_size", F.when(F.col("serving_size").between(1, 50), F.col("serving_size")))
      .withColumn("cooking_time", F.col("cooking_time_raw").try_cast("int"))
      .withColumn("ingredients", clean_text(F.col("ingredients_raw")))
      .withColumn("ingredient_list", parse_ingredients_udf(F.col("ingredients_raw")))
      .withColumn("preparation", clean_text(F.col("preparation_raw")))
      .withColumn("cooking_method", clean_text(F.col("method_raw")))
      .withColumn("serving_tips", clean_text(F.col("serving_tips_raw")))
      .withColumn("tips", clean_text(F.col("tips_raw")))
      .withColumn("name_key", name_key(F.col("dish_name")))
      # Tags: tach theo dau phay, chu thuong, bo trung, bo tag trung ten mon / tag chung chung
      .withColumn("dish_tags", F.array_distinct(F.filter(
          F.transform(F.split(nfc_udf(F.col("tags_raw")), ","),
                      lambda t: F.trim(F.regexp_replace(F.lower(t), r"\s+", " "))),
          lambda t: (F.length(t) > 1) & (t != F.col("name_key")) & ~t.isin(TAG_BLACKLIST))))
      .withColumn("dish_tags", F.coalesce("dish_tags", F.array().cast("array<string>")))
      .withColumn("image_link", F.when(F.col("image_raw").startswith("http"), F.trim("image_raw")))
      .withColumn("calories", F.col("calories").try_cast("int"))
      .withColumn("fat", F.col("fat").try_cast("int"))
      .withColumn("fiber", F.col("fiber").try_cast("int"))
      .withColumn("sugar", F.col("sugar").try_cast("int"))
      .withColumn("protein", F.col("protein").try_cast("int"))
      .cache())

# ---------------------------------------------------------------------------
# 3. Khu trung lap: cung nguon + cung ten + cung nguyen lieu + cung cach lam la MOT mon
#    (Cooky co cong thuc bi cao 2 lan, chi khac calo/thoi gian nau duoc sinh ngau nhien)
# ---------------------------------------------------------------------------
w_dup = Window.partitionBy("source", "name_key", "ingredients", "cooking_method").orderBy("source_stt")
df = df.withColumn("_rn", F.row_number().over(w_dup))
report["exact_duplicates_removed"] = df.filter("_rn > 1").count()
df = df.filter("_rn = 1").drop("_rn")

# ---------------------------------------------------------------------------
# 4. Gan food_id: giu id cu cua foods.csv (ghep theo image_link + ten mon goc),
#    mon moi nhan id tu 4001
# ---------------------------------------------------------------------------
def letters(c):
    """300 chu cai dau tien cua cach lam (bo dau cach, so, dau cau) - dung de so do giong nhau."""
    return F.substring(F.regexp_replace(F.lower(nfc_udf(c)), r"[^\p{L}]", ""), 1, 300)


old = (read_csv(spark, f"{P.raw}/foods.csv")
       .select(F.col("food_id").cast("int").alias("old_id"),
               F.trim(nfc_udf("dish_name")).alias("k_name"),
               F.trim("image_link").alias("k_img"),
               letters("cooking_method").alias("old_method")))
# 4 mon bi nhan doi trong foods.csv -> id nho nhat la id chinh thuc
w_key = Window.partitionBy("k_img", "k_name")
old = old.withColumn("canonical_id", F.min("old_id").over(w_key))

keys = df.select("source", "source_stt", F.trim(nfc_udf("name_raw")).alias("k_name"),
                 F.col("image_link").alias("k_img"), letters("method_raw").alias("raw_method"))
# Neu 1 id cu khop nhieu cong thuc raw (vd "Bánh xèo Nhật Bản" co 2 phien ban cung ten, cung anh)
# -> chon cong thuc co cach lam giong ban trong foods.csv nhat (khoang cach Levenshtein nho nhat)
cand = (keys.join(old.filter("old_id = canonical_id"), ["k_img", "k_name"])
            .withColumn("dist", F.levenshtein("raw_method", "old_method")))
report["old_ids_with_several_raw_candidates"] = (
    cand.groupBy("canonical_id").count().filter("count > 1").count())
w_best = Window.partitionBy("canonical_id").orderBy("dist", "source_stt")
id_map = (cand.withColumn("_rn", F.row_number().over(w_best)).filter("_rn = 1")
              .select("source", "source_stt", F.col("canonical_id").alias("food_id")))
report["old_ids_matched"] = id_map.count()
report["old_rows_unmatched"] = old.join(keys, ["k_img", "k_name"], "left_anti").count()

df = df.join(id_map, ["source", "source_stt"], "left")
w_new = Window.orderBy(F.when(F.col("source") == "mnmn", 0).otherwise(1), "source_stt")
new_ids = (df.filter(F.col("food_id").isNull()).select("source", "source_stt")
             .withColumn("new_id", F.row_number().over(w_new) + NEW_ID_START - 1))
df = (df.join(new_ids, ["source", "source_stt"], "left")
        .withColumn("in_original_clean", F.col("food_id").isNotNull())
        .withColumn("food_id", F.coalesce("food_id", "new_id")))

# Ten mon trung giua 2 nguon / trong cung nguon nhung KHAC cong thuc: giu ca hai, danh dau nhom
w_name = Window.partitionBy("name_key")
df = df.withColumn("dup_name_group",
                   F.when(F.count("*").over(w_name) > 1, F.min("food_id").over(w_name)))

foods = df.select(
    "food_id", "dish_name", "description", "dish_type", "serving_size", "cooking_time",
    "ingredients", "ingredient_list", "preparation", "cooking_method", "serving_tips", "tips",
    "dish_tags", "calories", "fat", "fiber", "sugar", "protein", "image_link",
    "source", "source_stt", "in_original_clean", "dup_name_group",
).orderBy("food_id").cache()

# ---------------------------------------------------------------------------
# 5. Ratings v2: doi id cua mon bi nhan doi ve id chinh thuc, bo foodId khong ton tai (4000),
#    user cham ca 2 ban sao -> lay trung binh (lam tron ve buoc 0,5)
# ---------------------------------------------------------------------------
r = read_csv(spark, f"{P.raw}/ratings.csv").select(
    F.col("userId").cast("int").alias("user_id"), F.col("foodId").cast("int").alias("old_id"),
    F.col("rating").cast("double").alias("rating"))
report["ratings_raw_rows"] = r.count()
r = r.join(old.select("old_id", "canonical_id"), "old_id", "left")
report["ratings_orphan_removed"] = r.filter(F.col("canonical_id").isNull()).count()
r = r.filter(F.col("canonical_id").isNotNull())
ratings = (r.groupBy("user_id", F.col("canonical_id").alias("food_id"))
             .agg(F.avg("rating").alias("rating"), F.count("*").alias("_n")))
report["ratings_merged_duplicates"] = ratings.filter("_n > 1").count()
ratings = (ratings.withColumn("rating", F.round(F.col("rating") * 2) / 2).drop("_n")
                  .orderBy("user_id", "food_id").cache())

# ---------------------------------------------------------------------------
# 6. Ghi ket qua
# ---------------------------------------------------------------------------
T.mark("write_hdfs")
foods.write.mode("overwrite").parquet(f"{P.curated}/foods")
ratings.write.mode("overwrite").parquet(f"{P.curated}/ratings_original")

T.mark("export_local")
os.makedirs(P.processed_local, exist_ok=True)
os.makedirs(P.output_local, exist_ok=True)
for fmt in ("parquet", "csv"):
    export_single(foods, os.path.join(P.processed_local, f"foods_v2.{fmt}"), fmt)
    export_single(ratings, os.path.join(P.processed_local, f"ratings_v2.{fmt}"), fmt)

T.mark("report")
report.update({
    "foods_v2_rows": foods.count(),
    "foods_from_original_clean": foods.filter("in_original_clean").count(),
    "foods_new": foods.filter("NOT in_original_clean").count(),
    "foods_by_source": {r_["source"]: r_["count"] for r_ in foods.groupBy("source").count().collect()},
    "dup_name_rows_kept": foods.filter(F.col("dup_name_group").isNotNull()).count(),
    "serving_size_set_null": foods.filter(F.col("serving_size").isNull()).count(),
    "no_image": foods.filter(F.col("image_link").isNull()).count(),
    "ratings_v2_rows": ratings.count(),
})
T.mark()
report["timings_s"] = T.parts
report["total_seconds"] = T.total()
with open(os.path.join(P.output_local, "clean_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
spark.stop()
