"""
03_features.py - Lam giau dac trung mon an tu van ban THAT cua foods_v2.

Dau vao : HDFS /data/curated/foods   (ket qua 02_clean.py)
Dau ra  : HDFS /data/features/dish_features   (Parquet - dau vao cua 04, 05, 06)
          data/processed/dish_features.{parquet,csv}   (xem tren may)
          data/output/features_report.json             (do phu, phan bo tung thuoc tinh)
          data/output/features_check_sample.csv        (100 mon ngau nhien de kiem tra tay)

Phuong phap: tu dien tu khoa + luat uu tien, viet hoan toan bang ham Spark
(regexp_instr / rlike / regexp_replace) nen chay phan tan, khong can UDF Python.
  - Uu tien TEN MON truoc, NGUYEN LIEU sau (ten mon noi ro mon chinh hon).
  - Khi ten mon co nhieu tu khoa, lay tu khoa xuat hien SOM NHAT trong ten
    ("Trứng chiên thịt" -> trứng; "Gỏi miến thịt bằm" -> gỏi).
  - Ranh gioi tu tieng Viet: (?<!\\p{L})tu_khoa(?!\\p{L}) de "cá" khong khop "các", "cà".
  - Truoc khi so khop, thay the cac cum de nham: "trứng gà" -> "trứng",
    "nấm đùi gà" -> "nấm", "hạt nêm vị gà" -> "hạt nêm", "mắm tôm" -> "mắm"...

Chay tren cum:  spark-submit src/03_features.py   (hoac python src/03_features.py trong terminal Jupyter)
Chay thu local: python src/03_features.py --local
"""
import argparse
import json
import os
import sys

from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, export_single, get_spark  # noqa: E402


# ===========================================================================
# 1. TU DIEN TU KHOA
# ===========================================================================
def rx(words):
    """Danh sach tu khoa -> regex co ranh gioi tu (tu dai dat truoc de khop uu tien)."""
    words = sorted(set(words), key=len, reverse=True)
    return r"(?<!\p{L})(?:" + "|".join(words) + r")(?!\p{L})"


# Cac cum gay nham -> thay bang tu trung tinh TRUOC khi tim tu khoa
CONFUSING = [
    (r"trứng (?:gà|vịt|cút|vịt lộn|muối|non)", "trứng"),
    (r"nấm (?:đùi gà|bào ngư|chân gà)", "nấm"),
    (r"đậu gà", "đậu"),
    (r"(?:hạt nêm|bột nêm|viên nêm|nước dùng|nước cốt|nước luộc|nước hầm|xương hầm|gia vị)"
     r"(?: vị| nấu| hầm)? (?:gà|bò|heo|tôm|sườn|xương)", "gia vị"),
    (r"mắm (?:tôm|ruốc|tép|cá)", "mắm"),
    (r"mỡ hành", "hành phi"),
    (r"ớt (?:chuông|đà lạt|ngọt)", "ớt chuông"),
    (r"bánh tráng", "bánhtráng"),     # banh trang la vo cuon, khong phai mon banh
]

# ---- Nhom dam (thu tu = uu tien khi hoa vi tri) ----
PROTEINS = [
    ("hải sản", ["tôm", "mực", "cua", "ghẹ", "nghêu", "ngao", "sò", "sò điệp", "cồi sò", "hàu",
                 "ốc", "hến", "bạch tuộc", "hải sâm", "tôm hùm", "sứa", "trai", "điệp", "tép",
                 "ruốc", "hải sản", "surimi", "thanh cua", "chem chép", "vẹm", "ngán", "sò lông", "sò huyết",
                 "bề bề", "tôm tít", "ghẹ biển", "cù kỳ", "sá sùng", "bào ngư"]),
    ("cá", ["cá", "lươn", "cá hồi", "cá ngừ", "chả cá", "cá viên", "khô cá", "cá khô"]),
    ("bò", ["bò", "bê", "thịt bò", "bắp bò", "gân bò", "bò viên", "beef", "bò bít tết"]),
    ("gà", ["gà", "thịt gà", "cánh gà", "đùi gà", "ức gà", "chân gà", "gà ta", "chicken"]),
    ("vịt", ["vịt", "ngan", "ngỗng", "duck"]),
    ("heo", ["heo", "lợn", "thịt ba chỉ", "ba chỉ", "ba rọi", "sườn", "sườn non", "giò heo",
             "chân giò", "thịt nạc", "nạc vai", "nạc dăm", "thịt xay", "thịt băm", "thịt heo",
             "chả lụa", "giò lụa", "giò sống", "lạp xưởng", "lạp xường", "xúc xích", "thịt xông khói",
             "bacon", "dăm bông", "jambon", "pate", "patê", "da heo", "thịt nguội",
             "dồi", "tim heo", "gan heo", "cật", "thịt heo bằm", "thịt heo xay"]),
    ("thịt khác", ["dê", "cừu", "ếch", "thỏ", "chim cút", "bồ câu", "đà điểu", "nai", "nhộng", "nhộng tằm", "chim", "cút", "ba ba", "rùa", "cá sấu"]),
    ("trứng", ["trứng", "lòng đỏ", "lòng trắng", "egg"]),
    ("đậu hũ/chay", ["đậu hũ", "đậu phụ", "tàu hũ", "tàu hủ", "tàu hũ ky", "tàu hủ ky", "đậu hủ",
                     "váng đậu", "chả chay", "giò chay", "nấm", "mì căn", "đậu nành", "chay"]),
]
# Tu chung chung ("thịt", "bì", "lòng") -> mac dinh la heo, nhung chi xet SAU cung, khi khong co nhom nao khac
GENERIC_PORK = [("heo", ["thịt", "bì", "lòng", "ham", "sườn", "bao tử", "dạ dày", "thịt viên"])
]
# Dong vat (de xac dinh mon chay): moi nhom dam tru dau hu/chay, cong nuoc mam, mo, huyet...
ANIMAL = [w for g, ws in PROTEINS if g != "đậu hũ/chay" for w in ws] + \
         ["thịt", "bì", "lòng", "nước mắm", "mắm", "mỡ", "huyết", "gan", "xương", "gelatin", "mỡ heo", "mỡ gà"]

# ---- Nhom mon (theo TEN MON; khi trung vi tri, nhom dung truoc thang) ----
CATEGORIES = [
    ("đồ uống", ["sinh tố", "nước ép", "smoothie", "cocktail", "mocktail", "latte", "cappuccino",
                 "cà phê", "cafe", "coffee", "trà", "trà sữa", "soda", "đá xay", "kombucha", "detox",
                 "milkshake",
                 "milk tea", "matcha đá", "siro", "rượu", "punch", "yakult", "ca cao", "cacao",
                 "chocolate nóng", "socola nóng"]),
    ("chè/tráng miệng", ["chè", "thạch", "rau câu", "pudding", "flan", "caramen", "sữa chua",
                         "yaourt", "yogurt", "tào phớ", "tàu hũ nước đường", "sương sáo", "panna cotta",
                         "mousse", "kem", "trái cây dầm", "hoa quả dầm", "sâm bổ lượng", "tiramisu",
                         "cheesecake", "mứt", "kẹo", "chocolate", "socola", "đậu hũ non đường"]),
    ("ăn vặt", ["bánhtráng trộn", "bánhtráng nướng", "bánhtráng cuốn", "snack", "bỏng ngô",
                "khoai tây chiên", "khoai lang chiên", "chips", "khô gà", "khô bò", "ô mai",
                "hạt điều rang", "đậu phộng rang", "xiên", "cá viên chiên", "bò viên chiên",
                "nem chua rán", "bắp xào", "ngô xào", "popcorn", "nachos", "khoai lắc"]),
    ("lẩu", ["lẩu"]),
    ("bún/phở/mì/miến", ["bún", "phở", "mì", "mỳ", "miến", "hủ tiếu", "hủ tíu", "bánh canh",
                         "bánh đa", "bánh phở", "bánh hỏi", "nui", "spaghetti", "pasta", "udon",
                         "ramen", "cao lầu", "mì quảng", "soba", "macaroni", "lasagna", "mỳ ý", "mì ý"]),
    ("canh/súp", ["canh", "súp", "soup", "xúp", "canh chua"]),
    ("gỏi/salad", ["gỏi", "nộm", "salad", "xà lách trộn", "trộn", "gỏi cuốn"]),
    ("cơm/xôi/cháo", ["cơm", "xôi", "cháo", "cơm chiên", "cơm rang", "cơm tấm", "risotto",
                      "sushi", "kimbap", "gimbap", "onigiri", "bibimbap", "paella", "cơm cuộn"]),
    ("bánh", ["bánh", "pizza", "cake", "cookie", "muffin", "tart", "pie", "sandwich", "hamburger",
              "burger", "waffle", "pancake", "bánh mì", "croissant", "donut", "cupcake", "brownie",
              "macaron", "crepe", "bread", "quiche", "dimsum", "há cảo", "xíu mại", "sủi cảo",
              "hoành thánh", "taco", "burrito"]),
]
DEFAULT_CATEGORY = "món chính"

# ---- Cach che bien ----
METHODS = [
    ("chiên", ["chiên", "rán", "chiên giòn", "chiên xù", "áp chảo", "rang", "tempura", "fried"]),
    ("xào", ["xào", "xào lăn", "xào tỏi"]),
    ("nướng", ["nướng", "quay", "bbq", "đút lò", "nướng mọi", "bỏ lò", "grill", "nướng giấy bạc"]),
    ("hấp", ["hấp", "hấp cách thủy", "hấp gừng"]),
    ("luộc", ["luộc", "chần", "trụng", "nhúng", "tái"]),
    ("kho/rim", ["kho", "rim", "om", "ram", "kho tộ", "kho tiêu", "kho quẹt", "ngào"]),
    ("hầm/nấu", ["hầm", "ninh", "tiềm", "nấu", "canh", "súp", "lẩu", "cháo", "chè", "sốt vang", "cà ri", "cari", "curry"]),
    ("trộn/gỏi", ["trộn", "gỏi", "nộm", "salad", "gỏi cuốn", "tái chanh", "muối chua", "dầm"]),
    ("pha/xay", ["sinh tố", "đá xay", "smoothie", "nước ép", "pha chế"]),
]
# Dong tu dem trong phan "cach lam" (khi ten mon khong noi cach che bien)
METHOD_VERBS = {
    "chiên": ["chiên", "rán"], "xào": ["xào"], "nướng": ["nướng", "quay", "lò nướng"],
    "hấp": ["hấp"], "luộc": ["luộc", "chần", "trụng"], "kho/rim": ["kho", "rim", "om"],
    "hầm/nấu": ["hầm", "ninh", "nấu", "đun sôi"],
}
CATEGORY_DEFAULT_METHOD = {"đồ uống": "pha/xay", "lẩu": "hầm/nấu", "canh/súp": "hầm/nấu",
                           "gỏi/salad": "trộn/gỏi"}

# ---- Cay ----
SPICY_NAME = ["cay", "ớt", "sa tế", "satế", "kim chi", "tê cay", "chua cay", "mala", "tokbokki",
              "tteokbokki", "buldak", "wasabi", "mù tạt", "spicy", "ớt xiêm", "tương ớt"]
SPICY_ING = ["sa tế", "ớt bột", "ớt khô", "ớt hiểm", "ớt xiêm", "tương ớt hàn quốc", "gochujang",
             "kim chi", "bột ớt", "dầu ớt", "ớt sa tế", "mù tạt", "wasabi"]

# ---- Mua ----
SEASON = [
    ("tết", ["bánh chưng", "bánh tét", "thịt kho trứng", "thịt kho hột vịt", "thịt kho tàu",
             "dưa hành", "củ kiệu", "canh khổ qua", "canh mướp đắng", "mứt", "xôi gấc", "giò thủ",
             "thịt đông", "chè kho", "bánh tổ", "tết"]),
    ("lạnh", ["lẩu", "hầm", "tiềm", "cháo", "súp", "cà ri", "cari", "sốt vang", "ninh",
              "chè nóng", "trà gừng", "chè gừng", "ấm bụng"]),
    ("nóng", ["chè", "kem", "sinh tố", "nước ép", "thạch", "rau câu", "sương sáo", "đá xay",
              "soda", "trà", "gỏi", "nộm", "salad", "sữa chua", "trái cây dầm", "smoothie",
              "thanh mát", "giải nhiệt", "canh chua", "nước ép", "nước chanh", "nước dừa", "mùa hè", "ngày hè"]),
]

# ===========================================================================
# 2. HAM SPARK
# ===========================================================================
def normalized(col):
    """Chu thuong + thay cac cum de nham."""
    x = F.lower(col)
    for pat, rep in CONFUSING:
        x = F.regexp_replace(x, rf"(?<!\p{{L}}){pat}(?!\p{{L}})", rep)
    return x


def pos(text, words):
    """Vi tri xuat hien som nhat cua 1 trong cac tu khoa (0 neu khong co)."""
    return F.coalesce(F.regexp_instr(text, F.lit(rx(words))), F.lit(0))


def first_match(text, groups, default=None):
    """Nhom co tu khoa xuat hien som nhat trong text; hoa vi tri -> nhom dung truoc trong danh sach."""
    # xep hang = vi tri * 100 + thu tu nhom ; bo nhom khong khop
    big = F.lit(10 ** 9)
    ranks = [F.when(pos(text, ws) > 0, pos(text, ws) * 100 + i).otherwise(big)
             for i, (_, ws) in enumerate(groups)]
    best = F.least(*ranks) if len(ranks) > 1 else ranks[0]
    expr = F.lit(default) if default is not None else F.lit(None).cast("string")
    for i, (g, _) in enumerate(groups):
        expr = F.when((best != big) & (best % 100 == i), F.lit(g)).otherwise(expr)
    return expr


def all_matches(text, groups):
    """Mang cac nhom co tu khoa trong text (theo thu tu trong danh sach)."""
    return F.filter(F.array(*[F.when(text.rlike(rx(ws)), F.lit(g)) for g, ws in groups]),
                    lambda x: x.isNotNull())


def count_words(text, words):
    return F.size(F.split(F.coalesce(text, F.lit("")), rx(words))) - 1


# ===========================================================================
# 3. CHUONG TRINH CHINH
# ===========================================================================
ap = argparse.ArgumentParser()
ap.add_argument("--local", action="store_true", help="chay Spark local, doc data/processed/foods_v2.parquet")
args = ap.parse_args()

spark = get_spark("03_features", local=args.local)
P = Paths(local=args.local)

if args.local:
    foods = spark.read.parquet("file://" + os.path.join(P.processed_local, "foods_v2.parquet"))
else:
    foods = spark.read.parquet(f"{P.curated}/foods")

df = (foods
      .withColumn("name_t", normalized(F.col("dish_name")))
      .withColumn("ing_t", normalized(F.array_join(F.col("ingredient_list"), " ; ")))
      .withColumn("tags_t", normalized(F.array_join(F.coalesce(F.col("dish_tags"), F.array()), " ; ")))
      .withColumn("how_t", normalized(F.concat_ws(" ", F.col("preparation"), F.col("cooking_method")))))

# ---- 3.1 Mon chay ----
name_says_veg = F.col("name_t").rlike(rx(["chay"])) | F.col("tags_t").rlike(rx(["món chay", "chay"]))
has_animal = F.col("ing_t").rlike(rx(ANIMAL)) | F.col("name_t").rlike(rx(ANIMAL))
df = df.withColumn("is_vegetarian", name_says_veg | ~has_animal)

# ---- 3.2 Nhom dam ----
# Mon chay ("Vịt quay chay") -> chi xet nhom chay, khong de chu "vịt" danh lua
veg_groups = [g for g in PROTEINS if g[0] == "đậu hũ/chay"]
p_name = first_match(F.col("name_t"), PROTEINS)
p_ing = first_match(F.col("ing_t"), PROTEINS)
df = (df
      .withColumn("proteins", F.when(F.col("is_vegetarian"),
                                     all_matches(F.concat_ws(" ", "name_t", "ing_t"), veg_groups))
                  .otherwise(F.array_distinct(F.concat(all_matches(F.col("name_t"), PROTEINS),
                                                       all_matches(F.col("ing_t"), PROTEINS)))))
      .withColumn("main_protein",
                  F.when(F.col("is_vegetarian") & (F.size("proteins") > 0), F.lit("đậu hũ/chay"))
                  .when(F.col("is_vegetarian"), F.lit("không"))
                  .otherwise(F.coalesce(p_name, first_match(F.col("name_t"), GENERIC_PORK), p_ing,
                                        first_match(F.col("ing_t"), GENERIC_PORK), F.lit("không")))))

# ---- 3.3 Nhom mon (chi theo ten mon; khong khop -> "món chính") ----
DRINK_START = (r"^(?:nước|sữa|trà|cà phê|cafe)\s(?!chấm|sốt|xốt|mắm|dùng|tương|màu|cốt|lèo|béo|"
               r"luộc|hầm|ướp|trộn|chua(?!\s*ngọt\s*uống))")
name_cat = F.regexp_replace(F.col("name_t"), rx(["cá cơm", "cơm dừa", "cơm mẻ", "kem phô mai", "kem tươi",
                                                   "kem sữa", "kem bơ"]), " x ")
df = df.withColumn("name_cat", name_cat)
df = df.withColumn("dish_category",
                   F.when(F.col("name_t").rlike(DRINK_START) & ~F.col("name_t").rlike(rx(["sữa chua", "trà xanh nướng"])),
                          F.lit("đồ uống"))
                    .otherwise(first_match(F.col("name_cat"), CATEGORIES, DEFAULT_CATEGORY)))
# Mon khong co ten nhom nhung nguyen lieu toan la do uong/ngot it gap -> giu "món chính"

# ---- 3.4 Cach che bien ----
verb_counts = [(m, count_words(F.col("how_t"), ws)) for m, ws in METHOD_VERBS.items()]
max_cnt = F.greatest(*[c for _, c in verb_counts])
text_method = F.lit(None).cast("string")
for m, c in reversed(verb_counts):          # hoa so lan -> phuong phap dung truoc thang
    text_method = F.when((c == max_cnt) & (c > 0), F.lit(m)).otherwise(text_method)
cat_default = F.lit(None).cast("string")
for cat, m in CATEGORY_DEFAULT_METHOD.items():
    cat_default = F.when(F.col("dish_category") == cat, F.lit(m)).otherwise(cat_default)

df = (df
      .withColumn("_name_methods", all_matches(F.col("name_t"), METHODS))
      .withColumn("_text_methods", F.filter(F.array(*[F.when(c >= 2, F.lit(m)) for m, c in verb_counts]),
                                            lambda x: x.isNotNull()))
      .withColumn("cooking_methods", F.array_distinct(F.concat("_name_methods", "_text_methods")))
      .withColumn("main_method", F.coalesce(first_match(F.col("name_t"), METHODS), cat_default,
                                            text_method, F.lit("khác"))))

# ---- 3.5 Loai mon da sua ----
SWEET = ["đường", "đường phèn", "đường thốt nốt", "đường nâu", "đường đen", "sữa đặc", "mật ong",
         "siro", "vani", "chocolate", "socola", "bột cacao", "kem tươi", "whipping cream", "mạch nha"]
SAVORY = ["nước mắm", "mắm", "hạt nêm", "bột nêm", "bột ngọt", "nước tương", "xì dầu", "dầu hào",
          "tiêu", "tiêu xay", "tỏi", "hành", "hành tím", "hành tây", "hành lá", "gia vị", "tương ớt",
          "sa tế", "ngũ vị hương", "bột canh", "hạt nêm chay"]
savory_bake = F.col("ing_t").rlike(rx([w for g, ws in PROTEINS if g not in ("trứng", "đậu hũ/chay") for w in ws]))
sweet_profile = F.col("ing_t").rlike(rx(SWEET)) & ~F.col("ing_t").rlike(rx(SAVORY)) & ~savory_bake
df = df.withColumn("sweet_profile", sweet_profile)
df = df.withColumn(
    "dish_type_fixed",
    F.when(F.col("dish_category") == "đồ uống", "Đồ uống")
     .when(F.col("dish_category") == "chè/tráng miệng", "Món ngọt")
     .when((F.col("dish_category") == "bánh") & ~savory_bake & ~F.col("name_t").rlike(rx(["mặn", "xèo", "cuốn", "bột lọc", "bao", "khọt", "căn"])), "Món ngọt")
     .when(F.col("sweet_profile") & (F.col("dish_category") != "gỏi/salad"), "Món ngọt")
     .when(F.col("is_vegetarian"), "Món chay")
     .otherwise("Món mặn"))

# Mon ngot / do uong: khong co "nhom dam chinh". Mon man khong co dam (nom dua leo, bi xao toi...) -> "rau củ"
df = df.withColumn("main_protein", F.when(F.col("dish_type_fixed").isin("Món ngọt", "Đồ uống"), F.lit("không"))
                                    .when(F.col("main_protein") == "không", F.lit("rau củ"))
                                    .otherwise(F.col("main_protein")))

# ---- 3.6 Cay ----
sweet_or_drink = F.col("dish_type_fixed").isin("Đồ uống", "Món ngọt")
df = df.withColumn("is_spicy", ~sweet_or_drink & (F.col("name_t").rlike(rx(SPICY_NAME))
                                                  | F.col("tags_t").rlike(rx(["cay"]))
                                                  | F.col("ing_t").rlike(rx(SPICY_ING))))

# ---- 3.7 Do phuc tap: so nguyen lieu, so tu trong so che + cach lam ----
df = (df.withColumn("n_ingredients", F.size("ingredient_list"))
        .withColumn("method_words", F.size(F.split(F.trim(F.col("how_t")), r"\s+"))))
# Cooky viet cach lam dai hon MNMN nhieu -> xep hang so tu TRONG TUNG NGUON (percent_rank)
from pyspark.sql import Window  # noqa: E402
w_src = Window.partitionBy("source").orderBy("method_words")
w_ing = Window.partitionBy("source").orderBy("n_ingredients")
df = (df.withColumn("words_rank", F.percent_rank().over(w_src))
        .withColumn("ing_rank", F.percent_rank().over(w_ing))
        .withColumn("is_quick", (F.col("words_rank") <= 0.4) & (F.col("ing_rank") <= 0.5)))
ING_Q40, WORDS_Q40 = "top 50% it nguyen lieu trong nguon", "top 40% it chu trong nguon"

# ---- 3.8 Mua (ten mon + tags; uu tien tết > lạnh > nóng) ----
season_text = F.concat_ws(" ; ", "name_t", "tags_t")
cool_ok = F.col("dish_category").isin("đồ uống", "chè/tráng miệng", "gỏi/salad") | \
    season_text.rlike(rx(["giải nhiệt", "thanh mát", "canh chua", "mùa hè", "ngày hè"]))
season_expr = F.lit("không")
for s, ws in reversed(SEASON):
    cond = season_text.rlike(rx(ws))
    if s == "nóng":
        cond = cond & cool_ok
    season_expr = F.when(cond, F.lit(s)).otherwise(season_expr)
df = df.withColumn("season", season_expr)

# ---- 3.9 Bua an phu hop ----
cat = F.col("dish_category")
breakfast_name = F.col("name_t").rlike(rx(["bánh mì", "xôi", "cháo", "phở", "bún", "hủ tiếu", "bánh cuốn",
                                           "sandwich", "pancake", "trứng ốp", "ốp la", "bánh bao",
                                           "yến mạch", "ngũ cốc", "granola", "sữa", "sinh tố"]))
meal = (F.when(cat == "đồ uống", F.array(F.lit("sáng"), F.lit("ăn vặt")))
         .when(cat.isin("chè/tráng miệng", "ăn vặt"), F.array(F.lit("ăn vặt")))
         .when((cat == "bánh") & (F.col("dish_type_fixed") == "Món ngọt"), F.array(F.lit("sáng"), F.lit("ăn vặt")))
         .when(cat == "bánh", F.array(F.lit("sáng"), F.lit("ăn vặt"), F.lit("tối")))
         .when(cat == "bún/phở/mì/miến", F.array(F.lit("sáng"), F.lit("trưa"), F.lit("tối")))
         .when(cat == "lẩu", F.array(F.lit("tối")))
         .when(cat == "cơm/xôi/cháo", F.when(F.col("name_t").rlike(rx(["xôi", "cháo"])),
                                              F.array(F.lit("sáng"), F.lit("tối")))
               .otherwise(F.array(F.lit("trưa"), F.lit("tối"))))
         .otherwise(F.array(F.lit("trưa"), F.lit("tối"))))
df = df.withColumn("meal_types", F.when(breakfast_name & ~F.array_contains(meal, "sáng"),
                                        F.concat(F.array(F.lit("sáng")), meal)).otherwise(meal))

# ===========================================================================
# 4. GHI KET QUA
# ===========================================================================
COLS = ["food_id", "dish_name", "source", "proteins", "main_protein", "cooking_methods", "main_method",
        "dish_category", "dish_type_fixed", "is_vegetarian", "is_spicy", "n_ingredients",
        "method_words", "is_quick", "season", "meal_types"]
feat = df.select(*COLS).orderBy("food_id").cache()
n = feat.count()

out_dir = f"{P.features}/dish_features"
feat.write.mode("overwrite").parquet(out_dir)
os.makedirs(P.processed_local, exist_ok=True)
os.makedirs(P.output_local, exist_ok=True)
for fmt in ("parquet", "csv"):
    export_single(feat, os.path.join(P.processed_local, f"dish_features.{fmt}"), fmt)


def dist(col):
    rows = feat.groupBy(col).count().orderBy(F.desc("count")).collect()
    return {str(r[col]): r["count"] for r in rows}


def dist_array(col):
    rows = feat.select(F.explode(col).alias("v")).groupBy("v").count().orderBy(F.desc("count")).collect()
    return {r["v"]: r["count"] for r in rows}


old_vs_new = feat.join(foods.select("food_id", "dish_type"), "food_id") \
                 .groupBy("dish_type", "dish_type_fixed").count().orderBy("dish_type", F.desc("count")).collect()
report = {
    "rows": n,
    "coverage": {
        "main_protein_known": feat.filter("main_protein != 'không'").count(),
        "dish_category_not_default": feat.filter(F.col("dish_category") != DEFAULT_CATEGORY).count(),
        "main_method_known": feat.filter("main_method != 'khác'").count(),
        "season_tagged": feat.filter("season != 'không'").count(),
    },
    "thresholds_is_quick": {"n_ingredients_q40": ING_Q40, "method_words_q40": WORDS_Q40},
    "main_protein": dist("main_protein"),
    "dish_category": dist("dish_category"),
    "main_method": dist("main_method"),
    "dish_type_fixed": dist("dish_type_fixed"),
    "dish_type_old_vs_fixed": [f"{r['dish_type']} -> {r['dish_type_fixed']}: {r['count']}" for r in old_vs_new],
    "is_vegetarian": dist("is_vegetarian"),
    "is_spicy": dist("is_spicy"),
    "is_quick": dist("is_quick"),
    "season": dist("season"),
    "meal_types": dist_array("meal_types"),
    "quick_by_source": {f"{r['source']}|{r['is_quick']}": r["count"]
                        for r in feat.groupBy("source", "is_quick").count().collect()},
}
with open(os.path.join(P.output_local, "features_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)

# 100 mon ngau nhien de nhom kiem tra tay (dien dung/sai vao cot 'kiem_tra')
sample = (feat.join(foods.select("food_id", F.array_join("ingredient_list", ", ").alias("nguyen_lieu")), "food_id")
              .orderBy(F.rand(42)).limit(100)
              .select("food_id", "dish_name", "nguyen_lieu", "main_protein", "main_method", "dish_category",
                      "dish_type_fixed", "is_vegetarian", "is_spicy", "season",
                      F.lit("").alias("kiem_tra"), F.lit("").alias("ghi_chu")))
export_single(sample, os.path.join(P.output_local, "features_check_sample.csv"), "csv")

print(json.dumps(report, ensure_ascii=False, indent=2))
spark.stop()
