"""
common.py - Ham dung chung cho toan bo pipeline ViFood Big Data.

  - get_spark()      : tao SparkSession (cum Docker hoac local de chay thu)
  - Paths            : duong dan HDFS / local cho tung tang du lieu
  - clean_text()     : lam sach van ban tieng Viet bang ham Spark (chay phan tan)
  - parse_ingredients: tach chuoi nguyen lieu thanh danh sach ten nguyen lieu
  - export_single()  : ghi 1 bang nho ra 1 file duy nhat de mo xem tren may
"""
import glob
import os
import re
import shutil
import unicodedata

from pyspark.sql import SparkSession, functions as F, types as T

# ---------------------------------------------------------------------------
# SparkSession va duong dan
# ---------------------------------------------------------------------------
PROJECT_DIR = os.getenv("PROJECT_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
HDFS_URL = os.getenv("HDFS_URL", "hdfs://namenode:8020")
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
DRIVER_HOST = os.getenv("SPARK_DRIVER_HOST", "jupyter")
EVENT_LOG_DIR = os.path.join(PROJECT_DIR, "logs", "spark-events")


def get_spark(app_name: str, local: bool = False) -> SparkSession:
    """local=True: chay Spark tren 1 may (de thu nhanh). Mac dinh: nop job len cum Docker."""
    b = SparkSession.builder.appName(app_name)
    if local:
        b = b.master("local[*]")
    else:
        b = (b.master(SPARK_MASTER)
             .config("spark.driver.host", DRIVER_HOST)
             .config("spark.executor.memory", "2g")
             .config("spark.hadoop.fs.defaultFS", HDFS_URL))
    # Event log -> logs/spark-events (thu muc du an, mount o moi container) de Spark History Server
    # (http://localhost:18080) xem lai cac job da chay xong: chup anh UI, do hieu nang
    os.makedirs(EVENT_LOG_DIR, exist_ok=True)
    b = (b.config("spark.eventLog.enabled", "true")
          .config("spark.eventLog.dir", "file://" + EVENT_LOG_DIR))
    spark = (b.config("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh")
              .config("spark.sql.shuffle.partitions", "8")
              .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    # Gui kem file nay cho cac worker: UDF dinh nghia o day can import duoc 'common' tren worker
    spark.sparkContext.addPyFile(os.path.abspath(__file__))
    return spark


class Paths:
    """Cac tang du lieu. Tren cum: HDFS /data/... ; khi local: thu muc data/ cua du an."""

    def __init__(self, local: bool = False):
        root = f"file://{PROJECT_DIR}/data/hdfs_local" if local else f"{HDFS_URL}/data"
        self.raw = f"file://{PROJECT_DIR}/data/raw" if local else f"{root}/raw"
        self.curated = f"{root}/curated"
        self.features = f"{root}/features"
        self.events = f"{root}/events"
        self.results = f"{root}/results"
        # Thu muc tren may (mount vao container tai /home/jovyan/work)
        self.processed_local = os.path.join(PROJECT_DIR, "data", "processed")
        self.output_local = os.path.join(PROJECT_DIR, "data", "output")


def read_csv(spark, path):
    """Doc CSV co o nhieu dong (phan Cach lam cua MNMN chua ky tu xuong dong)."""
    return (spark.read.option("header", True).option("multiLine", True)
            .option("quote", '"').option("escape", '"').option("encoding", "UTF-8")
            .csv(path))


# ---------------------------------------------------------------------------
# Chuan hoa van ban tieng Viet
# ---------------------------------------------------------------------------
def nfc(s):
    return unicodedata.normalize("NFC", s) if s is not None else None


nfc_udf = F.udf(nfc, T.StringType())


def clean_text(c):
    """
    Lam sach mot cot van ban. Tung buoc deu la ham Spark (regexp_replace) nen chay
    phan tan tren cac worker; rieng buoc NFC dung UDF Python.
      1. Chuan hoa Unicode ve NFC (GIU dau - khong xoa ky tu dau to hop nhu ban clean goc)
      2. Tab, xuong dong, khoang trang khong ngat -> dau cach
      3. Bo ky hieu ®, ™, emoji (giu ky hieu do °)
      4. Viet tat cua Mon Ngon Moi Ngay: so + M -> "muong canh", so + m -> "muong ca phe"
         (chi khi dung ngay sau con so, khong dung cham vao chu nam giua tu)
      5. Gach dau dong "–", "•" giua cac buoc -> dau cham ngat cau
      6. Them dau cach sau dau cham dinh lien chu hoa: "long.Sot" -> "long. Sot"
      7. Sua khoang trang quanh dau phay / dau cham, gop khoang trang thua
    """
    x = nfc_udf(c)
    x = F.regexp_replace(x, r"[\t\n\r\x{00A0}\x{2028}\x{2029}]+", " ")
    x = F.regexp_replace(x, r"[\p{So}&&[^°]]|[\x{FE0F}\x{200D}\x{200B}]", "")
    x = F.regexp_replace(x, r"(?<=[\d½¼¾/])\s?M(?![\p{L}\p{N}])", " muỗng canh")
    x = F.regexp_replace(x, r"(?<=[\d½¼¾/])\s?m(?![\p{L}\p{N}])", " muỗng cà phê")
    x = F.regexp_replace(x, r"(?i)(muỗng|thìa)\s+cf(?![\p{L}])", "$1 cà phê")      # Cooky: "muỗng cf"
    x = F.regexp_replace(x, r"(?i)(?<=\d)(?=(muỗng|thìa|chén|bát|giờ|tiếng|phút|lít|quả|trái|củ|cái)(?![\p{L}]))", " ")
    x = F.regexp_replace(x, r"(?<!\d)\s*(?:[–•◦]|\*(?=\s))+\s*(?=\p{L})", ". ")
    x = F.regexp_replace(x, r"([.!?])(?=\p{Lu})", "$1 ")
    x = F.regexp_replace(x, r"(?<=\p{L}):(?=[\p{L}\d])", ": ")                    # "ướp:1" -> "ướp: 1"
    x = F.regexp_replace(x, r"\s+([,.;:!?])", "$1")
    x = F.regexp_replace(x, r",(?=[^\s\d])", ", ")
    x = F.regexp_replace(x, r"([.,;:])(\s*[.,;:])+", "$1")
    x = F.regexp_replace(x, r"\s{2,}", " ")
    x = F.regexp_replace(x, r"^[\s.,;:\-]+|[\s,;:\-]+$", "")
    return F.when(F.length(x) > 0, x)


def fix_word_case(c):
    """
    Chi sua nhung tu bi viet hoa loi o giua tu: 'SữA' -> 'Sữa', 'TráI' -> 'Trái', 'PanCake' -> 'Pancake'.
    Giu nguyen tu viet hoa toan bo (BBQ, TẾT) va chu hoa cua dia danh (Hà Tĩnh).
    """
    words = F.split(c, " ")
    fixed = F.transform(words, lambda w: F.when(
        w.rlike(r"^\p{L}\p{Ll}*\p{Lu}") & (w != F.upper(w)),
        F.concat(F.upper(F.substring(w, 1, 1)), F.lower(F.substring(w, 2, 1000)))).otherwise(w))
    out = F.array_join(fixed, " ")
    return F.concat(F.upper(F.substring(out, 1, 1)), F.substring(out, 2, 100000))


def name_key(c):
    """Khoa so sanh ten mon: chu thuong, chi giu chu va so."""
    return F.trim(F.regexp_replace(F.lower(nfc_udf(c)), r"[^\p{L}\p{N}]+", " "))


# ---------------------------------------------------------------------------
# Tach nguyen lieu
# ---------------------------------------------------------------------------
_SPLIT = re.compile(r"(?<!\d),|,(?!\d)|;")
_LABEL = re.compile(
    r"^(gia vị|ăn kèm|rau nêm|rau ăn kèm|nước chấm|nước sốt|nước xốt|xốt|sốt|phần nhân|nhân|"
    r"phần vỏ|vỏ bánh|phần bánh|nguyên liệu|trang trí|topping|nước dùng|ướp|phần xốt|phần sốt|"
    r"dùng kèm|khác)\b", re.I)
_UNITS = (r"g|gr|gram|gam|kg|ml|l|lít|muỗng canh|muỗng cà phê|muỗng|thìa canh|thìa cà phê|thìa|"
          r"chén|bát|quả|trái|củ|cái|cây|con|miếng|lát|tép|nhánh|gói|hộp|lon|chai|ly|tô|bó|nắm|"
          r"lá|cọng|viên|khúc|ít|chút")
_LEAD_QTY = re.compile(rf"^[+\d½¼¾/.,\s\-]+(?:({_UNITS})\b)?\s*", re.I)
_DROP = {"", "và", "hoặc", "ít", "chút", "vừa đủ"}
# Doan sau dau phay chi la mo ta so che ("10 trái nhỏ, đập dập") -> khong phai nguyen lieu
_PREP_ONLY = re.compile(
    r"^(đập dập|đập|thái|cắt|băm|bỏ|rửa|làm sạch|gọt|ngâm|xay|nạo|bào|lọc|bóc|tách|lột|giã|"
    r"luộc|hấp|chiên|nướng|để|vắt|ép|loại|nhỏ|lớn|vừa|to|tươi)\b")


def parse_ingredients(s):
    """
    'Thịt bò xay 100g, Gia vị: muối, đường, Bột ngọt AJI-NO-MOTO®'
      -> ['thịt bò xay', 'muối', 'đường', 'bột ngọt']
    Quy tac: tach theo dau phay (khong tach so thap phan '1,5'); nhan dang 'Gia vị:' thi lay
    phan sau dau hai cham, con 'Mực ống: 600g' thi lay phan truoc; bo noi dung trong ngoac,
    trong ngoac kep va ten thuong hieu (tu co ®/™); cat tai con so dau tien (dinh luong).
    """
    if not s:
        return []
    s = unicodedata.normalize("NFC", s).replace("\t", " ").replace("\xa0", " ")
    # bo ngoac va ngoac kep TRUOC khi tach, vi ben trong co dau phay: "(bỏ cọng, cắt sợi)"
    s = re.sub(r"\([^)]*\)|\"[^\"]*\"|“[^”]*”", " ", s)
    out = []
    for seg in _SPLIT.split(s):
        seg = seg.strip()
        if ":" in seg:
            a, b = (t.strip() for t in seg.split(":", 1))
            seg = b if (_LABEL.match(a) or (a.isupper() and len(a) > 2)) else a
        seg = re.split(r"\S*[®™]", seg)[0]
        head = re.split(r"[\d½¼¾]", seg, maxsplit=1)[0]
        if not head.strip(" .-–*+&"):            # dang '2 quả trứng gà'
            head = re.split(r"[\d½¼¾]", _LEAD_QTY.sub("", seg), maxsplit=1)[0]
        name = re.sub(r"\s+", " ", head.lower()).strip(" .:-–*+&'\"")
        name = re.sub(r"^(và|hoặc|thêm)\s+", "", name)
        if _PREP_ONLY.match(name):
            continue
        if name not in _DROP and 2 <= len(name) <= 40 and len(name.split()) <= 6 and name not in out:
            out.append(name)
    return out


parse_ingredients_udf = F.udf(parse_ingredients, T.ArrayType(T.StringType()))


# ---------------------------------------------------------------------------
# Xuat 1 file de xem tren may
# ---------------------------------------------------------------------------
def export_single(df, local_path: str, fmt: str = "parquet"):
    """
    Spark luon ghi ra THU MUC gom nhieu file part-*. Ham nay gom ve 1 partition,
    ghi vao thu muc tam roi doi ten thanh 1 file duy nhat, vd data/processed/foods_v2.csv.
    Cac cot mang (array) duoc noi bang ' | ' khi ghi CSV.
    """
    tmp = local_path + "._tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    if fmt == "csv":
        for f in df.schema.fields:
            if isinstance(f.dataType, T.ArrayType):
                df = df.withColumn(f.name, F.concat_ws(" | ", f.name))
        (df.coalesce(1).write.mode("overwrite").option("header", True)
           .option("quote", '"').option("escape", '"').csv("file://" + tmp))
    else:
        df.coalesce(1).write.mode("overwrite").parquet("file://" + tmp)
    part = glob.glob(os.path.join(tmp, f"part-*.{'csv' if fmt == 'csv' else 'parquet'}"))[0]
    if os.path.exists(local_path):
        os.remove(local_path)
    shutil.move(part, local_path)
    shutil.rmtree(tmp, ignore_errors=True)
