"""
make_sample.py - Trich data/sample/: vai tram dong moi bang de xem nhanh cau truc du lieu ma khong can dung cum.

Chon co dinh (chay lai ra cung ket qua):
  - user: user_id % 167 == 0 (~300 user); events: su kien cua cac user nay trong 21-27/09/2026, 500 dong dau
  - mon: food_id % 18 == 0 (~300 mon) cho foods, dish_features
  - ratings_original: 300 dong co (user_id, food_id) nho nhat theo hash
  - recs_final: 6 user mau x 50 mon
  - raw: 300 dong dau cua moi file CSV goc (doc tu data/raw tren may)
Moi file la CSV UTF-8 (cot mang -> chuoi JSON). Du lieu hanh vi la MO PHONG.

Dau vao : HDFS /data/{curated,features,events,results/models/recs_final}, data/raw/*.csv
Dau ra  : data/sample/*.csv, data/sample/README.md (so dong, so cot)
Chay tren cum (tu may, xem CLAUDE.md):
  python scripts/make_sample.py
"""
import json
import os
import sys

import pandas as pd
from pyspark.sql import functions as F, types as T

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from common import PROJECT_DIR, Paths, get_spark  # noqa: E402

OUT = os.path.join(PROJECT_DIR, "data", "sample")
RAW = ["food_dataset_cookyweb.csv", "food_dataset_mnmnweb.csv", "foods.csv", "ratings.csv"]
N = 300


def to_pandas(df):
    """Cot mang / struct -> chuoi JSON de ghi CSV."""
    for f in df.schema.fields:
        if isinstance(f.dataType, (T.ArrayType, T.MapType, T.StructType)):
            df = df.withColumn(f.name, F.to_json(F.col(f.name)))
    return df.toPandas()


def main():
    os.makedirs(OUT, exist_ok=True)
    P = Paths()
    spark = get_spark("make_sample")
    users = spark.read.parquet(f"{P.events}/users").where(F.col("user_id") % 167 == 0)
    ids = [r.user_id for r in users.select("user_id").collect()]
    tables = {
        "users": users.orderBy("user_id"),
        "users_truth": spark.read.parquet(f"{P.events}/users_truth").where(F.col("user_id").isin(ids)).orderBy("user_id"),
        "events": (spark.read.parquet(f"{P.events}/events")
                   .where(F.col("user_id").isin(ids) & (F.col("ts") >= "2026-09-21") & (F.col("ts") < "2026-09-28"))
                   .orderBy("user_id", "ts").limit(500)),
        "foods": spark.read.parquet(f"{P.curated}/foods").where(F.col("food_id") % 18 == 0).orderBy("food_id"),
        "dish_features": spark.read.parquet(f"{P.features}/dish_features").where(F.col("food_id") % 18 == 0)
                         .orderBy("food_id"),
        "ratings_original": spark.read.parquet(f"{P.curated}/ratings_original")
                            .orderBy(F.xxhash64("user_id", "food_id"), "user_id", "food_id").limit(N),
        "recs_final": spark.read.parquet(f"{P.results}/models/recs_final").where(F.col("user_id").isin(ids[:6]))
                      .orderBy("user_id", "rank"),
    }
    info = {}
    for name, df in tables.items():
        pdf = to_pandas(df)
        pdf.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8")
        info[name] = (len(pdf), list(pdf.columns))
        print(f"[sample] {name}: {len(pdf)} dong, {len(pdf.columns)} cot", flush=True)
    spark.stop()
    for f in RAW:
        pdf = pd.read_csv(os.path.join(PROJECT_DIR, "data", "raw", f), nrows=N)
        pdf.to_csv(os.path.join(OUT, f"raw_{f}"), index=False, encoding="utf-8")
        info[f"raw_{f[:-4]}"] = (len(pdf), list(pdf.columns))
        print(f"[sample] raw_{f}: {len(pdf)} dong", flush=True)

    lines = ["# data/sample", "",
             "Vài trăm dòng mỗi bảng, trích bằng `scripts/make_sample.py` để xem cấu trúc dữ liệu mà không cần dựng cụm.",
             "Dữ liệu hành vi (users, events, recs_final) là **mô phỏng**. Ý nghĩa từng cột: `docs/DATA_DICTIONARY.md`.",
             "Cột mảng ghi dạng chuỗi JSON.", "",
             "| File | Nguồn | Cách chọn | Số dòng | Số cột |", "|---|---|---|---|---|"]
    how = {"users": ("HDFS /data/events/users", "user_id % 167 = 0"),
           "users_truth": ("HDFS /data/events/users_truth", "cùng user với users.csv"),
           "events": ("HDFS /data/events/events", "user mẫu, 21–27/09/2026, 500 dòng đầu theo user, ts"),
           "foods": ("HDFS /data/curated/foods", "food_id % 18 = 0"),
           "dish_features": ("HDFS /data/features/dish_features", "food_id % 18 = 0"),
           "ratings_original": ("HDFS /data/curated/ratings_original", "300 dòng đầu theo hash (user_id, food_id)"),
           "recs_final": ("HDFS /data/results/models/recs_final", "6 user mẫu đầu tiên × 50 món")}
    for name, (n, cols) in info.items():
        src, sel = how.get(name, (f"data/raw/{name[4:]}.csv", "300 dòng đầu"))
        fname = f"{name}.csv"
        lines.append(f"| `{fname}` | {src} | {sel} | {n} | {len(cols)} |")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, "columns.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v[1] for k, v in info.items()}, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
