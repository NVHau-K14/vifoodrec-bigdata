"""
common.py - Ham dung chung cho toan bo pipeline ViFood Big Data.

  - get_spark()      : tao SparkSession (cum Docker hoac local de chay thu)
  - Paths            : duong dan HDFS / local cho tung tang du lieu
  - Timer            : do thoi gian tung giai doan (timings_s) + gan job group Spark cung ten
  - clean_text()     : lam sach van ban tieng Viet bang ham Spark (chay phan tan)
  - parse_ingredients: tach chuoi nguyen lieu thanh danh sach ten nguyen lieu
  - export_single()  : ghi 1 bang nho ra 1 file duy nhat de mo xem tren may
"""
import contextlib
import glob
import os
import re
import shutil
import time
import unicodedata

from pyspark import SparkContext
from pyspark.sql import SparkSession, functions as F, types as T

# ---------------------------------------------------------------------------
# SparkSession va duong dan
# ---------------------------------------------------------------------------
PROJECT_DIR = os.getenv("PROJECT_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
HDFS_URL = os.getenv("HDFS_URL", "hdfs://namenode:8020")
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
DRIVER_HOST = os.getenv("SPARK_DRIVER_HOST", "jupyter")
EVENT_LOG_DIR = os.path.join(PROJECT_DIR, "logs", "spark-events")
# Do hieu nang (D17, scripts/09_perf.py). Khong dat bien nao thi moi thu chay nhu cu.
DATA_ROOT = os.getenv("VIFOOD_DATA_ROOT", "/data")      # goc HDFS cua cac tang du lieu (vd /perf/s100)
OUTPUT_DIR = os.getenv("VIFOOD_OUTPUT_DIR")             # thu muc report (tuong doi thi tinh tu PROJECT_DIR)
RUN_TAG = os.getenv("VIFOOD_RUN_TAG")                   # gan vao ten ung dung, vd 06b_als|s100|w1|r2


def get_spark(app_name: str, local: bool = False, conf: dict = None) -> SparkSession:
    """local=True: chay Spark tren 1 may (de thu nhanh). Mac dinh: nop job len cum Docker.
    conf: ghi de cau hinh (vd luong Structured Streaming chi xin 2 core, driver 1g, D18)."""
    b = SparkSession.builder.appName(f"{app_name}|{RUN_TAG}" if RUN_TAG else app_name)
    if local:
        # local: driver kiem luon executor -> can nhieu bo nho hon (container jupyter gioi han 4g)
        b = b.master("local[*]").config("spark.driver.memory", "3g")
    else:
        b = (b.master(SPARK_MASTER)
             .config("spark.driver.memory", "2g")
             .config("spark.driver.host", DRIVER_HOST)
             .config("spark.executor.memory", "2g")
             .config("spark.hadoop.fs.defaultFS", HDFS_URL)
             # Client Hadoop mac dinh ghi 3 ban, cum chi co 2 DataNode -> thieu ban sao (D12)
             .config("spark.hadoop.dfs.replication", "2"))
    # Event log -> logs/spark-events (thu muc du an, mount o moi container) de Spark History Server
    # (http://localhost:18080) xem lai cac job da chay xong: chup anh UI, do hieu nang
    os.makedirs(EVENT_LOG_DIR, exist_ok=True)
    b = (b.config("spark.eventLog.enabled", "true")
          .config("spark.eventLog.dir", "file://" + EVENT_LOG_DIR))
    b = (b.config("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh")
          .config("spark.sql.shuffle.partitions", "8"))
    for k, v in (conf or {}).items():
        b = b.config(k, v)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    # Gui kem file nay cho cac worker: UDF dinh nghia o day can import duoc 'common' tren worker
    spark.sparkContext.addPyFile(os.path.abspath(__file__))
    return spark


class Paths:
    """
    Cac tang du lieu. Tren cum: HDFS /data/... ; khi local: thu muc data/ cua du an.
    Do hieu nang (D17): VIFOOD_DATA_ROOT doi goc HDFS (raw van doc /data/raw, checkpoint nam trong goc moi);
    VIFOOD_OUTPUT_DIR doi thu muc report va ban sao nho (processed_local = <thu muc>/processed).
    output_prod luon la data/output: --fixed doc tham so da chon cua ban that tu day.
    """

    def __init__(self, local: bool = False):
        root = f"file://{PROJECT_DIR}/data/hdfs_local" if local else f"{HDFS_URL}{DATA_ROOT}"
        self.raw = f"file://{PROJECT_DIR}/data/raw" if local else f"{HDFS_URL}/data/raw"
        self.curated = f"{root}/curated"
        self.features = f"{root}/features"
        self.events = f"{root}/events"
        self.results = f"{root}/results"
        self.models = f"{root}/models"           # model Spark da luu (buoc 06)
        if local or DATA_ROOT != "/data":
            self.checkpoint = f"{root}/_checkpoint"
        else:
            self.checkpoint = f"{HDFS_URL}/tmp/checkpoint"
        # Thu muc tren may (mount vao container tai /home/jovyan/work)
        self.output_prod = os.path.join(PROJECT_DIR, "data", "output")
        if OUTPUT_DIR:
            self.output_local = os.path.join(PROJECT_DIR, OUTPUT_DIR)     # OUTPUT_DIR tuyet doi thi giu nguyen
            self.processed_local = os.path.join(self.output_local, "processed")
        else:
            self.output_local = self.output_prod
            self.processed_local = os.path.join(PROJECT_DIR, "data", "processed")


class Timer:
    """
    Do thoi gian tung giai doan (dua vao timings_s cua report) va gan job group Spark trung ten giai doan,
    de phan do hieu nang (D17) gom so lieu stage tu History Server theo dung giai doan.
      with T("ten"): ...          khoi lenh
      T.mark("ten") / T.mark()    script khong chia khoi with: ket thuc giai doan dang mo, mo giai doan moi
    """

    def __init__(self, tag="06"):
        self.t0, self.parts, self.tag, self._open = time.time(), {}, tag, None

    @staticmethod
    def _group(name):
        sc = SparkContext._active_spark_context
        if sc is None:
            return
        if name:
            sc.setJobGroup(name, name)
        else:
            sc.setLocalProperty("spark.jobGroup.id", None)
            sc.setLocalProperty("spark.job.description", None)

    def _close(self, name, t):
        self.parts[name] = round(time.time() - t, 1)
        print(f"[{self.tag}] {name}: {self.parts[name]}s", flush=True)

    @contextlib.contextmanager
    def __call__(self, name):
        t = time.time()
        self._group(name)
        yield
        self._group(None)
        self._close(name, t)

    def mark(self, name=None):
        if self._open:
            self._close(*self._open)
        self._open = (name, time.time()) if name else None
        self._group(name)

    def total(self):
        return round(time.time() - self.t0, 1)


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
