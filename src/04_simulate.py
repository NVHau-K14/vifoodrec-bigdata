"""
04_simulate.py - Sinh du lieu HANH VI mo phong (users + events) bang Spark.

Ly do: ratings goc cua ViFoodRec la so ngau nhien (khong co tin hieu), nen nhom tu sinh
hanh vi co quy luat dua tren dac trung THAT cua mon an (dish_features tu buoc 03).

Dau vao : HDFS /data/features/dish_features        (ket qua 03_features.py)
Dau ra  : HDFS /data/events/users                  ho so nguoi dung (mo hinh DUOC dung)
          HDFS /data/events/users_truth            persona that (CHI de kiem chung, vd ARI cua K-means)
          HDFS /data/events/events/month=YYYY-MM/  su kien xem/luu/nau/cham diem (Parquet, chia theo thang)
          data/processed/users.{parquet,csv}, users_truth.csv
          data/output/events_sample.csv            toan bo su kien cua 200 user (de mo xem)
          data/output/simulate_report.json         so lieu kiem tra quy luat (dua vao bao cao)
          data/output/simulate_config.json         tham so + trong so persona (de tai lap / trinh bay)

Mo hinh sinh (moi user):
  diem_hop_khau_vi(mon) = w_user . x_mon                 (persona chinh + 0.5 * persona phu
                                                          + vung mien + nhom tuoi + nhieu ca nhan)
                        + LAT_W * u_user . v_mon         (so thich an - mo hinh CF hoc duoc, content thi khong)
                        - ZIPF * log(hang_pho_bien)      (do pho bien kieu Zipf)
                        + ngu_canh(bua, mua theo vung, cuoi tuan)
  Chon mon xem trong moi phien = lay mau softmax khong lap (Gumbel top-k).
  Pheu: xem -> luu (it hon) -> nau (phien nau) -> cham diem (mot lan / mon, sau khi nau).
  "Mam com": bua trua/toi co the nau them canh + rau di kem mon chinh (cho FP-Growth).
  Diem cham suy ra tu diem hop khau vi + chat luong mon + do khat khe cua user + nhieu.

Sinh PHAN TAN: bang users chia thanh nhieu partition, moi worker sinh su kien cho cac user
cua minh bang mapInPandas (numpy). Seed co dinh theo (SEED, user_id) nen ket qua
giong het nhau du chay 1 hay 2 worker, bao nhieu partition.

Chay tren cum (terminal Jupyter):
  python src/04_simulate.py --scale 0.01     # chay thu 1% (~500 user) truoc
  python src/04_simulate.py                  # day du 50.000 user
  python src/04_simulate.py --csv            # ghi them ban CSV de so sanh Parquet vs CSV
Chay thu local:  python src/04_simulate.py --local --scale 0.01
"""
import argparse
import calendar
import json
import os
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
from pyspark.sql import functions as F, types as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import Paths, export_single, get_spark  # noqa: E402

# ===========================================================================
# 0. THAM SO
# ===========================================================================
ap = argparse.ArgumentParser()
ap.add_argument("--local", action="store_true", help="chay Spark local (khong can cum)")
ap.add_argument("--users", type=int, default=50_000, help="so user o quy mo 100%%")
ap.add_argument("--scale", type=float, default=1.0, help="ti le quy mo, vd 0.01 = 1%% so user")
ap.add_argument("--seed", type=int, default=2026)
ap.add_argument("--partitions", type=int, default=0, help="so partition cua bang users (0 = tu chon)")
ap.add_argument("--csv", action="store_true", help="ghi them ban CSV len HDFS de so sanh dung luong voi Parquet")
args = ap.parse_args()

SEED = args.seed
N_USERS = max(50, int(round(args.users * args.scale)))
START = date(2025, 10, 1)
END = date(2026, 9, 30)
N_DAYS = (END - START).days + 1                      # 365
TET = date(2026, 2, 17)                              # mung 1 Tet Binh Ngo
START_EPOCH = calendar.timegm(START.timetuple()) - 7 * 3600   # 00:00 gio Viet Nam

# Cac he so chinh cua mo hinh sinh (ghi vao simulate_config.json)
CFG = dict(
    sub_weight=0.5,        # persona phu anh huong bang 1/2 persona chinh
    w_noise=0.35,          # do lech so thich ca nhan tren tung dac trung
    latent_k=8, latent_w=0.7,
    zipf=0.45,             # do doc cua phan phoi pho bien
    quality_sel=0.3,       # mon "ngon" (chat luong an) duoc chon nhieu hon chut
    temp=1.0,              # nhiet do softmax
    sessions_median=95,    # so phien / nam (trung vi) cua 1 user hoat dong ca nam
    sessions_sigma=0.75,
    views_mean=2.6,        # so mon xem them / phien (Poisson), toi da MAX_VIEWS
    max_views=12,
    recook=0.25,           # xac suat nau lai 1 mon da luu
    companion=0.5,         # xac suat canh di kem la "canh quen" cua mon chinh
    new_user_share=0.28,   # ti le user dang ky trong nam mo phong
    churn_share=0.12,
)

PERSONAS = ["ăn chay", "tập gym", "ăn kiêng", "mê hải sản", "bận rộn", "hảo ngọt",
            "gia đình truyền thống", "thích cay/nhậu"]
PERSONA_P = [0.08, 0.10, 0.10, 0.10, 0.18, 0.12, 0.20, 0.12]
REGIONS = ["Bắc", "Trung", "Nam"]
REGION_P = [0.35, 0.20, 0.45]
AGES = ["18-24", "25-34", "35-44", "45+"]
SLOTS = ["sáng", "trưa", "tối", "khuya"]
SLOT_HOURS = [(6, 9), (10, 13), (16, 20), (21, 24)]      # [gio bat dau, gio ket thuc)
SEASON_STATES = ["không", "lạnh", "nóng", "tết"]

# Trong so khau vi cua tung persona tren cac dac trung mon (xem build_features)
PERSONA_W = {
    "ăn chay": {"veg": 2.5, "t:Món chay": 1.5, "p:đậu hũ/chay": 1.0, "p:rau củ": 0.6, "animal": -4.0},
    "tập gym": {"p:gà": 1.2, "p:bò": 1.0, "p:trứng": 0.8, "p:cá": 0.6, "m:luộc": 0.6, "m:hấp": 0.5,
                "m:nướng": 0.4, "c:gỏi/salad": 0.4, "m:pha/xay": 0.3, "t:Món ngọt": -1.2, "m:chiên": -0.8},
    "ăn kiêng": {"c:gỏi/salad": 1.4, "m:hấp": 0.8, "m:luộc": 0.8, "p:rau củ": 0.8, "c:canh/súp": 0.6,
                 "veg": 0.3, "t:Đồ uống": 0.3, "t:Món ngọt": -1.5, "m:chiên": -1.2, "c:bánh": -0.6,
                 "complex": -0.2},
    "mê hải sản": {"p:hải sản": 2.2, "p:cá": 0.9, "m:nướng": 0.4, "m:hấp": 0.4, "c:lẩu": 0.6},
    "bận rộn": {"quick": 1.8, "complex": -0.8, "m:xào": 0.5, "m:chiên": 0.4, "p:trứng": 0.6,
                "c:bún/phở/mì/miến": 0.5, "c:cơm/xôi/cháo": 0.4, "c:lẩu": -1.0, "m:hầm/nấu": -0.4,
                "c:bánh": -0.5},
    "hảo ngọt": {"t:Món ngọt": 2.0, "c:chè/tráng miệng": 1.2, "c:bánh": 0.8, "t:Đồ uống": 1.0,
                 "c:ăn vặt": 0.4},
    "gia đình truyền thống": {"c:món chính": 1.0, "c:canh/súp": 1.2, "m:kho/rim": 1.0, "p:heo": 0.6,
                              "p:cá": 0.6, "p:rau củ": 0.4, "m:xào": 0.4, "foreign": -1.2,
                              "t:Đồ uống": -0.6, "c:bánh": -0.4},
    "thích cay/nhậu": {"spicy": 1.6, "m:nướng": 1.0, "c:lẩu": 1.0, "c:ăn vặt": 0.6, "c:gỏi/salad": 0.5,
                       "p:bò": 0.5, "p:thịt khác": 0.8, "p:hải sản": 0.5, "t:Món ngọt": -0.8},
}
# Vung mien: mon dac san cua vung minh + khau vi chung (mien Nam ngot, mien Trung cay)
REGION_W = {
    "Bắc": {"r:bắc": 0.8, "r:nam": -0.2, "c:canh/súp": 0.2, "m:luộc": 0.2},
    "Trung": {"r:trung": 0.8, "spicy": 0.5},
    "Nam": {"r:nam": 0.8, "r:bắc": -0.2, "t:Món ngọt": 0.25},
}
AGE_W = {
    "18-24": {"foreign": 0.6, "c:ăn vặt": 0.4, "t:Đồ uống": 0.4, "complex": -0.3},
    "25-34": {"foreign": 0.3, "quick": 0.2},
    "35-44": {"c:món chính": 0.2},
    "45+": {"foreign": -0.6, "c:canh/súp": 0.3, "complex": 0.2},
}
# Phan bo tuoi, ti le nam, khung bua theo persona chinh
AGE_P = {"ăn chay": [.15, .25, .25, .35], "tập gym": [.40, .40, .15, .05], "ăn kiêng": [.30, .40, .20, .10],
         "mê hải sản": [.20, .35, .25, .20], "bận rộn": [.20, .50, .25, .05], "hảo ngọt": [.45, .30, .15, .10],
         "gia đình truyền thống": [.05, .25, .35, .35], "thích cay/nhậu": [.20, .40, .30, .10]}
MALE_P = {"ăn chay": .45, "tập gym": .60, "ăn kiêng": .25, "mê hải sản": .50, "bận rộn": .50,
          "hảo ngọt": .30, "gia đình truyền thống": .30, "thích cay/nhậu": .70}
SLOT_P = {"ăn chay": [.22, .28, .42, .08], "tập gym": [.30, .27, .35, .08], "ăn kiêng": [.22, .30, .40, .08],
          "mê hải sản": [.15, .27, .45, .13], "bận rộn": [.10, .20, .60, .10], "hảo ngọt": [.20, .22, .38, .20],
          "gia đình truyền thống": [.13, .32, .50, .05], "thích cay/nhậu": [.10, .20, .40, .30]}
COOK_P = {"ăn chay": .40, "tập gym": .40, "ăn kiêng": .38, "mê hải sản": .38, "bận rộn": .25,
          "hảo ngọt": .30, "gia đình truyền thống": .50, "thích cay/nhậu": .30}
MAM_P = {"ăn chay": .35, "tập gym": .20, "ăn kiêng": .30, "mê hải sản": .30, "bận rộn": .10,
         "hảo ngọt": .15, "gia đình truyền thống": .60, "thích cay/nhậu": .20}
INCOMPATIBLE = {("ăn chay", "mê hải sản"), ("ăn chay", "thích cay/nhậu")}

# Thang mua theo vung (dung cho cot season cua mon); Tet dat len tren cung
COLD_MONTHS = {"Bắc": {11, 12, 1, 2}, "Trung": {11, 12, 1}, "Nam": {12, 1}}
HOT_MONTHS = {"Bắc": {5, 6, 7, 8}, "Trung": {4, 5, 6, 7, 8}, "Nam": {3, 4, 5, 6}}
TET_WINDOW = (TET - timedelta(days=21), TET + timedelta(days=6))

# Mon dac san vung mien / mon nuoc ngoai (nhan dang theo ten mon)
REGION_RX = {
    "bắc": r"hà nội|miền bắc|bắc bộ|kiểu bắc|hải phòng|nam định|thái bình|hạ long|sapa|sa pa|phở|bún chả|bún thang|bún riêu|"
           r"bún đậu|chả cá lã vọng|bánh cuốn|nem rán|xôi xéo|bánh đa cua|bánh đúc|canh cua|giò thủ|"
           r"bánh chưng|thắng cố|cốm",
    "trung": r"huế|quảng nam|quảng ngãi|quảng bình|quảng trị|miền trung|đà nẵng|hội an|nha trang|bình định|phú yên|nghệ an|hà tĩnh|bún bò|mì quảng|"
             r"cao lầu|bánh bèo|bánh nậm|bánh lọc|bánh căn|bún chả cá|cơm hến|bún hến|nem lụi|"
             r"bánh ít|tré",
    "nam": r"sài gòn|miền tây|nam bộ|cần thơ|bến tre|cà mau|châu đốc|sóc trăng|bạc liêu|hủ tiếu|hủ tíu|"
           r"bánh xèo|canh chua|kho tộ|bánh khọt|lẩu mắm|cơm tấm|bánh canh|gỏi cuốn|bánh tét|"
           r"bánh pía|cá lóc|bò bía|bánh bò|chè bưởi",
}
FOREIGN_RX = (r"pizza|spaghetti|mì ý|pasta|lasagna|burger|sandwich|steak|bít tết|salad|cookie|cupcake|"
              r"muffin|brownie|tiramisu|pudding|cheesecake|mousse|waffle|pancake|cake|sushi|kimbap|"
              r"tokbokki|tteok|ramen|udon|kim chi|kimchi|teriyaki|tempura|takoyaki|cà ri|curry|"
              r"taco|hàn quốc|kiểu hàn|nhật bản|kiểu nhật|thái lan|kiểu thái|kiểu ý|kiểu pháp|kiểu âu|kiểu mỹ|"
              r"singapore|đài loan|smoothie|latte|macaron|tart|"
              r"gimbap|bulgogi|dimsum|há cảo|xíu mại")

t0 = time.time()
spark = get_spark("04_simulate", local=args.local)
P = Paths(local=args.local)


# ===========================================================================
# 1. DAC TRUNG MON -> MA TRAN X (5.499 mon x ~45 cot), tinh tren driver (bang nho)
# ===========================================================================
def read_features():
    path = f"{P.features}/dish_features"
    try:
        return spark.read.parquet(path)
    except Exception:
        if not args.local:
            raise
        # local: neu chua chay 03 o che do local thi doc ban xuat ra data/processed
        return spark.read.parquet("file://" + os.path.join(P.processed_local, "dish_features.parquet"))


feat_df = read_features()
dishes = feat_df.toPandas().sort_values("food_id").reset_index(drop=True)
N_DISH = len(dishes)
name_l = dishes["dish_name"].str.lower()


def zscore_by(s, by):
    return s.groupby(by).transform(lambda v: (v - v.mean()) / (v.std() + 1e-9))


dishes["region_tag"] = "không"
for reg, pat in REGION_RX.items():
    hit = name_l.str.contains(rf"(?<!\w)(?:{pat})(?!\w)", regex=True) & (dishes["region_tag"] == "không")
    dishes.loc[hit, "region_tag"] = reg
dishes["is_foreign"] = name_l.str.contains(rf"(?<!\w)(?:{FOREIGN_RX})(?!\w)", regex=True)
dishes["complexity"] = (zscore_by(np.log1p(dishes["n_ingredients"]), dishes["source"])
                        + zscore_by(np.log1p(dishes["method_words"]), dishes["source"])) / 2


def build_features(d):
    cols = {}
    for v in sorted(d["main_protein"].unique()):
        cols[f"p:{v}"] = (d["main_protein"] == v).astype(float) + \
            0.4 * d["proteins"].apply(lambda a, v=v: v in list(a)).astype(float) * (d["main_protein"] != v)
    for v in sorted(d["main_method"].unique()):
        cols[f"m:{v}"] = (d["main_method"] == v).astype(float) + \
            0.3 * d["cooking_methods"].apply(lambda a, v=v: v in list(a)).astype(float) * (d["main_method"] != v)
    for v in sorted(d["dish_category"].unique()):
        cols[f"c:{v}"] = (d["dish_category"] == v).astype(float)
    for v in sorted(d["dish_type_fixed"].unique()):
        cols[f"t:{v}"] = (d["dish_type_fixed"] == v).astype(float)
    cols["veg"] = d["is_vegetarian"].astype(float)
    cols["animal"] = 1.0 - cols["veg"]
    cols["spicy"] = d["is_spicy"].astype(float)
    cols["quick"] = d["is_quick"].astype(float)
    cols["complex"] = d["complexity"].clip(-2.5, 2.5)
    for reg in REGION_RX:
        cols[f"r:{reg}"] = (d["region_tag"] == reg).astype(float)
    cols["foreign"] = d["is_foreign"].astype(float)
    return pd.DataFrame(cols)


Xdf = build_features(dishes)
FEATS = list(Xdf.columns)
X = Xdf.to_numpy(np.float32)


def wvec(spec):
    v = np.zeros(len(FEATS), np.float32)
    for k, w in spec.items():
        if k not in FEATS:
            raise KeyError(f"Dac trung '{k}' khong co trong dish_features: {FEATS}")
        v[FEATS.index(k)] = w
    return v


W_PERSONA = np.stack([wvec(PERSONA_W[p]) for p in PERSONAS])
W_REGION = np.stack([wvec(REGION_W[r]) for r in REGIONS])
W_AGE = np.stack([wvec(AGE_W[a]) for a in AGES])

# Thuoc tinh "an" cua mon (giong nhau cho moi user): chat luong, do pho bien, vector so thich
rng0 = np.random.default_rng(SEED)
quality = rng0.normal(0, 1, N_DISH).astype(np.float32)
pop_key = 0.6 * quality + 0.8 * rng0.normal(0, 1, N_DISH)
pop_rank = np.empty(N_DISH, np.int64)
pop_rank[np.argsort(-pop_key)] = np.arange(1, N_DISH + 1)
pop_term = (-CFG["zipf"] * np.log(pop_rank)).astype(np.float32)
pop_term -= pop_term.mean()
V_LAT = (rng0.normal(0, 1, (N_DISH, CFG["latent_k"])) / np.sqrt(CFG["latent_k"])).astype(np.float32)
item_base = pop_term + CFG["quality_sel"] * quality


# ---- Ngu canh: bua x trang thai mua x cuoi tuan -> vector cong them cho moi mon ----
def has_meal(t):
    return dishes["meal_types"].apply(lambda a: t in list(a)).to_numpy()


cat = dishes["dish_category"].to_numpy()
season = dishes["season"].to_numpy()
slot_bonus = []
for s, t in zip(SLOTS, ["sáng", "trưa", "tối", "ăn vặt"]):
    b = np.where(has_meal(t), 0.9, -1.0)
    if s == "khuya":
        b = np.where(np.isin(cat, ["lẩu"]) | (dishes["main_method"].to_numpy() == "nướng"), b + 0.8, b)
        b = np.where(cat == "đồ uống", b + 0.3, b)
    slot_bonus.append(b)
season_bonus = [np.zeros(N_DISH),
                np.select([season == "lạnh", season == "nóng"], [1.2, -0.6], 0.0),
                np.select([season == "nóng", season == "lạnh"], [1.0, -0.8], 0.0),
                np.select([season == "tết", season == "lạnh"], [2.0, 0.3], 0.0)]
quick = dishes["is_quick"].to_numpy()
wk_bonus = [np.where(quick, 0.3, 0.0) + np.where(cat == "lẩu", -0.4, 0.0),                 # ngay thuong
            np.where(quick, -0.3, 0.0) + np.where(cat == "lẩu", 0.6, 0.0)
            + np.where(dishes["main_method"].to_numpy() == "nướng", 0.3, 0.0)
            + 0.3 * dishes["complexity"].clip(-2, 2).to_numpy()]                          # cuoi tuan
CTX = np.zeros((len(SLOTS) * 4 * 2, N_DISH), np.float32)
for s in range(len(SLOTS)):
    for st in range(4):
        for wk in range(2):
            CTX[s * 8 + st * 2 + wk] = slot_bonus[s] + season_bonus[st] + wk_bonus[wk]

# ---- Lich: trong so hoat dong moi ngay va trang thai mua theo vung ----
days = [START + timedelta(days=i) for i in range(N_DAYS)]
day_w = np.array([[1.0, 0.95, 0.95, 1.0, 1.05, 1.3, 1.4][d.weekday()] for d in days])
for i, d in enumerate(days):
    if TET - timedelta(days=10) <= d < TET:
        day_w[i] *= 1.5            # tuan truoc Tet: tim cong thuc, nau nhieu
    elif TET <= d <= TET + timedelta(days=3):
        day_w[i] *= 0.6            # mung 1-4: an o nha ho hang, it nau
is_weekend = np.array([d.weekday() >= 5 for d in days], np.int64)
season_state = np.zeros((len(REGIONS), N_DAYS), np.int64)
for r, reg in enumerate(REGIONS):
    for i, d in enumerate(days):
        if TET_WINDOW[0] <= d <= TET_WINDOW[1]:
            season_state[r, i] = 3
        elif d.month in COLD_MONTHS[reg]:
            season_state[r, i] = 1
        elif d.month in HOT_MONTHS[reg]:
            season_state[r, i] = 2

# ---- "Mam com": canh quen cua tung mon chinh, danh sach canh va rau ----
is_veg = dishes["is_vegetarian"].to_numpy()
canh_idx = np.where(cat == "canh/súp")[0]
rau_idx = np.where((cat == "món chính") & np.isin(dishes["main_protein"].to_numpy(), ["rau củ", "đậu hũ/chay"])
                   & np.isin(dishes["main_method"].to_numpy(), ["xào", "luộc", "hấp"]))[0]
top_canh = canh_idx[np.argsort(pop_rank[canh_idx])][:40]
top_canh_veg = [i for i in canh_idx[np.argsort(pop_rank[canh_idx])] if is_veg[i]][:15]
companion = np.full(N_DISH, -1, np.int64)
main_idx = np.where(cat == "món chính")[0]
companion[main_idx] = np.where(is_veg[main_idx], rng0.choice(top_canh_veg, len(main_idx)),
                               rng0.choice(top_canh, len(main_idx)))

SIM = dict(
    seed=SEED, X=X, W_PERSONA=W_PERSONA, W_REGION=W_REGION, W_AGE=W_AGE, V=V_LAT,
    item_base=item_base, quality=quality, CTX=CTX, day_w=day_w, is_weekend=is_weekend,
    season_state=season_state, cat_main=(cat == "món chính"), companion=companion,
    canh_idx=canh_idx, rau_idx=rau_idx, food_id=dishes["food_id"].to_numpy(np.int64),
    slot_p=np.array([SLOT_P[p] for p in PERSONAS]), cook_p=np.array([COOK_P[p] for p in PERSONAS]),
    mam_p=np.array([MAM_P[p] for p in PERSONAS]), slot_hours=np.array(SLOT_HOURS),
    start_epoch=START_EPOCH, end_epoch=START_EPOCH + N_DAYS * 86400, cfg=CFG,
)


# ===========================================================================
# 2. BANG USERS (50.000 dong - sinh tren driver, du nho)
# ===========================================================================
def make_users(n):
    rng = np.random.default_rng(SEED + 1)
    uid = np.arange(1, n + 1)
    p_main = rng.choice(len(PERSONAS), n, p=PERSONA_P)
    p_sub = np.empty(n, np.int64)
    for i, pm in enumerate(p_main):
        pr = np.array(PERSONA_P, float)
        pr[pm] = 0
        for j, q in enumerate(PERSONAS):
            if (PERSONAS[pm], q) in INCOMPATIBLE or (q, PERSONAS[pm]) in INCOMPATIBLE:
                pr[j] = 0
        p_sub[i] = rng.choice(len(PERSONAS), p=pr / pr.sum())
    region = rng.choice(len(REGIONS), n, p=REGION_P)
    age = np.array([rng.choice(len(AGES), p=AGE_P[PERSONAS[pm]]) for pm in p_main])
    male = rng.random(n) < np.array([MALE_P[PERSONAS[pm]] for pm in p_main])
    device = rng.choice(["android", "ios", "web"], n, p=[.55, .35, .10])
    # Dang ky: user cu (dang ky truoc 01/10/2025) va user moi trong nam (tang dan ve cuoi nam)
    is_new = rng.random(n) < CFG["new_user_share"]
    start_day = np.where(is_new, np.minimum((rng.beta(1.4, 1.0, n) * N_DAYS).astype(int), N_DAYS - 7), 0)
    old_days = rng.integers(1, 640, n)                                  # tu 01/2024
    signup = [START + timedelta(days=int(s)) if new else START - timedelta(days=int(o))
              for s, new, o in zip(start_day, is_new, old_days)]
    churn = rng.random(n) < CFG["churn_share"]
    span = N_DAYS - 1 - start_day
    end_day = np.where(churn, start_day + (span * rng.uniform(0.2, 0.9, n)).astype(int) + 7, N_DAYS - 1)
    end_day = np.minimum(end_day, N_DAYS - 1)
    activity = np.clip(rng.lognormal(np.log(CFG["sessions_median"]), CFG["sessions_sigma"], n), 6, 700)
    rater = rng.beta(2, 3, n)
    fav_prop = rng.lognormal(0, 0.4, n)
    strict = rng.normal(0, 0.35, n)                                      # user khat khe / de tinh
    return pd.DataFrame(dict(
        user_id=uid.astype(np.int32), p_main=p_main, p_sub=p_sub, region_i=region, age_i=age,
        start_day=start_day.astype(np.int64), end_day=end_day.astype(np.int64),
        activity=activity, rater=rater, fav_prop=fav_prop, strict=strict,
        region=[REGIONS[r] for r in region], age_group=[AGES[a] for a in age],
        gender=np.where(male, "nam", "nữ"), device=device, signup_date=signup,
        persona_main=[PERSONAS[p] for p in p_main], persona_sub=[PERSONAS[p] for p in p_sub],
        churned=churn, last_active_date=[START + timedelta(days=int(e)) for e in end_day],
    ))


users_pd = make_users(N_USERS)
print(f"[04] {N_DISH} mon, {N_USERS} user, {len(FEATS)} dac trung mon")


# ===========================================================================
# 3. SINH SU KIEN CHO 1 USER (chay tren worker)
# ===========================================================================
def simulate_user(u, S):
    cfg = S["cfg"]
    rng = np.random.default_rng([S["seed"], int(u.user_id)])
    nf = S["X"].shape[1]
    w = (S["W_PERSONA"][u.p_main] + cfg["sub_weight"] * S["W_PERSONA"][u.p_sub]
         + S["W_REGION"][u.region_i] + S["W_AGE"][u.age_i] + rng.normal(0, cfg["w_noise"], nf))
    lat = rng.normal(0, 1, cfg["latent_k"])
    base = (S["X"] @ w + cfg["latent_w"] * (S["V"] @ lat) + S["item_base"]).astype(np.float64)
    z = (base - base.mean()) / (base.std() + 1e-9)            # muc hop khau vi chuan hoa theo user

    d0, d1 = int(u.start_day), int(u.end_day)
    dw = S["day_w"][d0:d1 + 1]
    n_sess = rng.poisson(u.activity * dw.sum() / S["day_w"].sum())
    if n_sess == 0:
        return None
    sday = np.sort(rng.choice(np.arange(d0, d1 + 1), size=n_sess, p=dw / dw.sum()))
    slot_p = rng.dirichlet(S["slot_p"][u.p_main] * 30)
    slot = rng.choice(4, n_sess, p=slot_p)
    wk = S["is_weekend"][sday]
    combo = slot * 8 + S["season_state"][u.region_i][sday] * 2 + wk
    hours = S["slot_hours"][slot]
    start_sec = (S["start_epoch"] + sday * 86400 + rng.integers(hours[:, 0], hours[:, 1]) * 3600
                 + rng.integers(0, 3600, n_sess))
    order = np.argsort(start_sec, kind="stable")          # session_id tang theo thoi gian
    sday, slot, wk, combo, start_sec = sday[order], slot[order], wk[order], combo[order], start_sec[order]
    p_cook = np.clip(S["cook_p"][u.p_main] + 0.15 * wk - 0.15 * (slot == 3), 0.05, 0.9)
    is_cook = rng.random(n_sess) < p_cook
    n_views = np.minimum(1 + rng.poisson(cfg["views_mean"], n_sess), cfg["max_views"])

    # Mon xem trong moi phien: softmax khong lap = Gumbel top-k, tinh theo tung nhom ngu canh
    K = cfg["max_views"]
    views = np.empty((n_sess, K), np.int64)
    for c in np.unique(combo):
        idx = np.where(combo == c)[0]
        g = (base + S["CTX"][c]) / cfg["temp"] + rng.gumbel(size=(len(idx), base.size))
        top = np.argpartition(-g, K, axis=1)[:, :K]
        order = np.argsort(-np.take_along_axis(g, top, 1), axis=1)
        views[idx] = np.take_along_axis(top, order, 1)

    def pick(cands, c):
        g = base[cands] + S["CTX"][c][cands] + rng.gumbel(size=len(cands))
        return int(cands[np.argmax(g)])

    E_f, E_t, E_ts, E_slot, E_sid, E_r = [], [], [], [], [], []

    def emit(d, typ, ts, s, r=np.nan):
        E_f.append(d); E_t.append(typ); E_ts.append(ts); E_slot.append(slot[s])
        E_sid.append(int(u.user_id) * 10_000 + s); E_r.append(r)

    favs, fav_set, rated = [], set(), set()
    p_fav_u = 0.10 * u.fav_prop
    for s in range(n_sess):
        t = int(start_sec[s])
        c = combo[s]
        seen = views[s, :n_views[s]]
        for d in seen:
            emit(d, 0, t, s)
            if d not in fav_set and rng.random() < p_fav_u / (1 + np.exp(-1.5 * (z[d] - 2.0))) * 2:
                emit(d, 1, t + int(rng.integers(5, 40)), s)
                fav_set.add(d); favs.append(d)
            t += int(rng.integers(30, 240))
        if not is_cook[s]:
            continue
        if favs and rng.random() < cfg["recook"]:
            main = favs[int(rng.integers(len(favs)))]
            emit(main, 0, t, s); t += int(rng.integers(30, 120))
        else:
            main = pick(seen, c)
        cooks = [main]
        if slot[s] in (1, 2) and S["cat_main"][main] and rng.random() < S["mam_p"][u.p_main]:
            canh = S["companion"][main] if rng.random() < cfg["companion"] else pick(S["canh_idx"], c)
            cooks.append(int(canh))
            if rng.random() < 0.35 and len(S["rau_idx"]):
                rau = pick(S["rau_idx"], c)
                if rau not in cooks:
                    cooks.append(rau)
            for d in cooks[1:]:
                emit(d, 0, t, s); t += int(rng.integers(30, 180))
        t_cook = t + int(rng.integers(600, 2700))
        for d in cooks:
            emit(d, 2, t_cook, s)
            if d not in rated and rng.random() < u.rater:
                r = (3.7 + 1.0 * (min(z[d], 3.5) - 2.2) + 0.4 * S["quality"][d] + u.strict
                     + rng.normal(0, 0.4))
                r = float(np.clip(np.round(r * 2) / 2, 0.5, 5.0))
                t_rate = t_cook + int(rng.integers(3600, 4 * 3600))
                if t_rate < S["end_epoch"]:
                    emit(d, 3, t_rate, s, r)
                    rated.add(d)
    keep = np.array(E_ts, np.int64) < S["end_epoch"]     # bo su kien tran sang sau 30/09/2026
    n = int(keep.sum())
    if n == 0:
        return None
    E_f, E_t, E_ts, E_slot, E_sid, E_r = (np.asarray(a)[keep] for a in (E_f, E_t, E_ts, E_slot, E_sid, E_r))
    return pd.DataFrame(dict(
        user_id=np.full(n, int(u.user_id), np.int32),
        food_id=S["food_id"][np.array(E_f, np.int64)].astype(np.int32),
        event_code=np.array(E_t, np.int8), ts_epoch=np.array(E_ts, np.int64),
        slot_code=np.array(E_slot, np.int8), session_id=np.array(E_sid, np.int64),
        rating=np.array(E_r, np.float32)))


def make_generator(S):
    def gen(batches):
        for pdf in batches:
            buf, rows = [], 0
            for u in pdf.itertuples(index=False):
                ev = simulate_user(u, S)
                if ev is not None:
                    buf.append(ev); rows += len(ev)
                if rows >= 200_000:
                    yield pd.concat(buf, ignore_index=True); buf, rows = [], 0
            if buf:
                yield pd.concat(buf, ignore_index=True)
    return gen


EV_SCHEMA = T.StructType([
    T.StructField("user_id", T.IntegerType()), T.StructField("food_id", T.IntegerType()),
    T.StructField("event_code", T.ByteType()), T.StructField("ts_epoch", T.LongType()),
    T.StructField("slot_code", T.ByteType()), T.StructField("session_id", T.LongType()),
    T.StructField("rating", T.FloatType())])

# ===========================================================================
# 4. CHAY SINH PHAN TAN + GHI HDFS
# ===========================================================================
SIM_COLS = ["user_id", "p_main", "p_sub", "region_i", "age_i", "start_day", "end_day",
            "activity", "rater", "fav_prop", "strict"]
n_parts = args.partitions or max(4, min(64, N_USERS // 1000 * 2 or 4))
users_sim = spark.createDataFrame(users_pd[SIM_COLS]).repartition(n_parts)

ev_types = F.element_at(F.array(*[F.lit(x) for x in ["view", "favorite", "cook", "rate"]]),
                        F.col("event_code").cast("int") + 1)
slot_names = F.element_at(F.array(*[F.lit(x) for x in SLOTS]), F.col("slot_code").cast("int") + 1)
events = (users_sim.mapInPandas(make_generator(SIM), EV_SCHEMA)
          .withColumn("ts", F.timestamp_seconds("ts_epoch"))
          .select("user_id", "food_id", ev_types.alias("event_type"), "ts", slot_names.alias("meal_slot"),
                  "session_id", "rating", F.date_format("ts", "yyyy-MM").alias("month")))

ev_path = f"{P.events}/events"
t1 = time.time()
(events.repartitionByRange(12, "month")
       .sortWithinPartitions("month", "user_id", "ts")
       .write.mode("overwrite").partitionBy("month").parquet(ev_path))
gen_seconds = round(time.time() - t1, 1)
print(f"[04] Da ghi events len {ev_path} sau {gen_seconds}s")

PUBLIC = ["user_id", "region", "age_group", "gender", "device", "signup_date"]
TRUTH = ["user_id", "persona_main", "persona_sub", "activity", "rater", "churned", "last_active_date"]
users_pub = spark.createDataFrame(users_pd[PUBLIC]).withColumn("signup_date", F.to_date("signup_date"))
users_truth = (spark.createDataFrame(users_pd[TRUTH].round({"activity": 1, "rater": 3})
                                     .rename(columns={"activity": "sessions_per_year", "rater": "rate_prob"}))
               .withColumn("last_active_date", F.to_date("last_active_date")))
users_pub.coalesce(1).write.mode("overwrite").parquet(f"{P.events}/users")
users_truth.coalesce(1).write.mode("overwrite").parquet(f"{P.events}/users_truth")

# ===========================================================================
# 5. KIEM TRA QUY LUAT -> simulate_report.json
# ===========================================================================
ev = spark.read.parquet(ev_path)
feat_small = feat_df.select("food_id", "dish_category", "main_protein", "dish_type_fixed",
                            "is_vegetarian", "is_spicy", "is_quick", "season")
truth_small = spark.createDataFrame(users_pd[["user_id", "persona_main", "region", "age_group"]])


def to_dict(rows, k, v="count"):
    return {str(r[k]): r[v] for r in rows}


by_type = to_dict(ev.groupBy("event_type").count().collect(), "event_type")
n_events = sum(by_type.values())
cooks = ev.filter("event_type = 'cook'").join(feat_small, "food_id").join(truth_small, "user_id").cache()
views = ev.filter("event_type = 'view'")


def share_by_persona(cond, name):
    rows = (cooks.groupBy("persona_main")
            .agg(F.round(F.avg(F.when(cond, 1.0).otherwise(0.0)) * 100, 1).alias(name)).collect())
    return {r["persona_main"]: r[name] for r in rows}


persona_check = {
    "% mon nau la mon chay (is_vegetarian)": share_by_persona(F.col("is_vegetarian"), "v"),
    "% mon nau la hai san": share_by_persona(F.col("main_protein") == "hải sản", "v"),
    "% mon nau la mon ngot/do uong": share_by_persona(F.col("dish_type_fixed").isin("Món ngọt", "Đồ uống"), "v"),
    "% mon nau la mon nhanh": share_by_persona(F.col("is_quick"), "v"),
    "% mon nau la mon cay": share_by_persona(F.col("is_spicy"), "v"),
    "% mon nau la canh/sup": share_by_persona(F.col("dish_category") == "canh/súp", "v"),
}
season_rows = (cooks.withColumn("m", F.date_format("ts", "yyyy-MM"))
               .groupBy("m", "region")
               .agg(F.round(F.avg(F.when(F.col("dish_category") == "lẩu", 1.0).otherwise(0.0)) * 100, 2).alias("lau"),
                    F.round(F.avg(F.when(F.col("season") == "tết", 1.0).otherwise(0.0)) * 100, 2).alias("tet"),
                    F.round(F.avg(F.when(F.col("season") == "nóng", 1.0).otherwise(0.0)) * 100, 2).alias("nong"))
               .orderBy("m", "region").collect())
slot_rows = (ev.filter("event_type = 'view'").join(feat_small, "food_id").groupBy("meal_slot", "dish_category")
             .count().collect())
slot_tot = {}
for r in slot_rows:
    slot_tot[r["meal_slot"]] = slot_tot.get(r["meal_slot"], 0) + r["count"]
top_cat_by_slot = {}
for s in SLOTS:
    rs = sorted([r for r in slot_rows if r["meal_slot"] == s], key=lambda r: -r["count"])[:4]
    top_cat_by_slot[s] = {r["dish_category"]: round(100 * r["count"] / slot_tot[s], 1) for r in rs}
ratings = ev.filter("event_type = 'rate'")
rating_stats = ratings.agg(F.round(F.avg("rating"), 3).alias("mean"), F.round(F.stddev("rating"), 3).alias("std"),
                           F.countDistinct("user_id").alias("users_rated")).first().asDict()
pairs = ev.select("user_id", "food_id").distinct().count()
active_users = ev.select("user_id").distinct().count()
per_user = ev.groupBy("user_id").count().select(F.percentile_approx("count", [0.1, 0.5, 0.9, 0.99]).alias("q")).first()["q"]
mam = (ev.filter("event_type = 'cook'").groupBy("session_id").count()
       .agg(F.round(F.avg(F.when(F.col("count") >= 2, 1.0).otherwise(0.0)) * 100, 1)).first()[0])
val_test = {m: ev.filter(F.col("month") == m).select("user_id").distinct().count() for m in ("2026-08", "2026-09")}
top_share = (views.groupBy("food_id").count().orderBy(F.desc("count")).limit(55)
             .agg(F.sum("count")).first()[0] or 0)



def hdfs_size(path):
    try:
        hp = spark._jvm.org.apache.hadoop.fs.Path(path)
        return hp.getFileSystem(spark._jsc.hadoopConfiguration()).getContentSummary(hp).getLength()
    except Exception as e:  # noqa: BLE001
        print("[04] Khong do duoc dung luong:", e)
        return None


hdfs_bytes = hdfs_size(ev_path)
csv_bytes = None
if args.csv:
    ev.write.mode("overwrite").option("header", True).partitionBy("month").csv(f"{P.events}/events_csv")
    csv_bytes = hdfs_size(f"{P.events}/events_csv")

report = {
    "scale": args.scale, "users": N_USERS, "active_users": active_users, "dishes": N_DISH,
    "period": f"{START} -> {END}", "seed": SEED,
    "events": n_events, "events_by_type": by_type,
    "events_by_month": to_dict(ev.groupBy("month").count().orderBy("month").collect(), "month"),
    "events_by_slot": to_dict(ev.groupBy("meal_slot").count().collect(), "meal_slot"),
    "events_by_weekday": to_dict(ev.groupBy(F.date_format("ts", "E").alias("d")).count().collect(), "d"),
    "events_per_user_p10_p50_p90_p99": per_user,
    "funnel": {"favorite/view %": round(100 * by_type.get("favorite", 0) / by_type["view"], 2),
               "cook/view %": round(100 * by_type.get("cook", 0) / by_type["view"], 2),
               "rate/cook %": round(100 * by_type.get("rate", 0) / max(1, by_type.get("cook", 0)), 2)},
    "rating": {**rating_stats,
               "distribution": to_dict(ratings.groupBy("rating").count().orderBy("rating").collect(), "rating")},
    "user_food_pairs": pairs, "density_%": round(100 * pairs / (active_users * N_DISH), 4),
    "views_share_top1pct_dishes_%": round(100 * top_share / by_type["view"], 1),
    "users_active_val_2026-08": val_test["2026-08"], "users_active_test_2026-09": val_test["2026-09"],
    "cook_sessions_with_2plus_dishes_%": mam,
    "persona_check_cook": persona_check,
    "top_category_by_slot_view_%": top_cat_by_slot,
    "season_check_cook_%": [f"{r['m']} {r['region']}: lẩu {r['lau']} | tết {r['tet']} | nóng {r['nong']}"
                            for r in season_rows],
    "dish_region_tags": dishes["region_tag"].value_counts().to_dict(),
    "dish_foreign": int(dishes["is_foreign"].sum()),
    "hdfs_bytes_events": hdfs_bytes,
    "hdfs_mb_events": round(hdfs_bytes / 2**20, 1) if hdfs_bytes else None,
    "hdfs_mb_events_csv": round(csv_bytes / 2**20, 1) if csv_bytes else None,
    "generate_write_seconds": gen_seconds,
    "total_seconds": None,
}

# ---- Xuat file de xem tren may ----
os.makedirs(P.processed_local, exist_ok=True)
os.makedirs(P.output_local, exist_ok=True)
for fmt in ("parquet", "csv"):
    export_single(users_pub, os.path.join(P.processed_local, f"users.{fmt}"), fmt)
export_single(users_truth, os.path.join(P.processed_local, "users_truth.csv"), "csv")
sample_users = [int(x) for x in np.random.default_rng(SEED + 7).choice(users_pd["user_id"], min(200, N_USERS),
                                                                       replace=False)]
export_single(ev.filter(F.col("user_id").isin(sample_users)).orderBy("user_id", "ts")
              .withColumn("ts", F.date_format("ts", "yyyy-MM-dd HH:mm:ss")),
              os.path.join(P.output_local, "events_sample.csv"), "csv")

report["total_seconds"] = round(time.time() - t0, 1)
with open(os.path.join(P.output_local, "simulate_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
config = {"CFG": CFG, "PERSONAS": dict(zip(PERSONAS, PERSONA_P)), "PERSONA_W": PERSONA_W,
          "REGION_W": REGION_W, "AGE_W": AGE_W, "SLOT_P": SLOT_P, "COOK_P": COOK_P, "MAM_P": MAM_P,
          "AGE_P": AGE_P, "MALE_P": MALE_P, "REGIONS": dict(zip(REGIONS, REGION_P)),
          "COLD_MONTHS": {k: sorted(v) for k, v in COLD_MONTHS.items()},
          "HOT_MONTHS": {k: sorted(v) for k, v in HOT_MONTHS.items()},
          "TET": str(TET), "TET_WINDOW": [str(x) for x in TET_WINDOW], "FEATURES": FEATS}
with open(os.path.join(P.output_local, "simulate_config.json"), "w", encoding="utf-8") as fh:
    json.dump(config, fh, ensure_ascii=False, indent=2)

print(json.dumps({k: report[k] for k in ["users", "events", "events_by_type", "funnel", "rating",
                                          "hdfs_mb_events", "total_seconds"]}, ensure_ascii=False, indent=2, default=str))
spark.stop()
