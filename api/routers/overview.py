"""E0 health, E1 overview (+ tien do pipeline), E22 danh sach gia tri cho bo loc."""
import time

from fastapi import APIRouter

from ..cache import cached
from ..db import db_name, get_db
from ..dishes_common import MEALS, categories

router = APIRouter(tags=["Tổng quan"])

# (buoc, ten, report trong collection reports; "perf" = collection perf (D17); None = khong co report rieng)
PIPELINE = [
    ("01", "Nạp dữ liệu vào HDFS", None),
    ("02", "Làm sạch", "clean_report"),
    ("03", "Đặc trưng món", "features_report"),
    ("04", "Sinh hành vi (mô phỏng)", "simulate_report"),
    ("05", "Phân tích hành vi", "analysis_report"),
    ("06", "Mô hình và đánh giá", "model_"),
    ("07", "Xuất MongoDB", None),
    ("08", "API và dashboard", None),
    ("09", "Đo hiệu năng Spark", "perf"),
    ("10", "Structured Streaming", None),
]


@router.get("/health", summary="E0 – tình trạng API và MongoDB")
def health():
    db = get_db()
    t = time.perf_counter()
    db.command("ping")
    ms = (time.perf_counter() - t) * 1000
    return {"status": "ok", "db": db_name(), "mongo_ms": round(ms, 2),
            "counts": {c: db[c].estimated_document_count() for c in ("dishes", "users", "recs")}}


@cached
def reports():
    return {r["_id"]: r["content"] for r in get_db().reports.find()}


def pipeline(ov):
    rep = reports()
    n_trending = get_db().trending.estimated_document_count()
    out = []
    for step, name, key in PIPELINE:
        seconds = None
        if key == "perf":
            status = "Xong" if get_db().perf.find_one({"_id": "summary"}, {"_id": 1}) else "Chưa"
        elif key == "model_":
            found = [v for k, v in rep.items() if k.startswith("model_")]
            seconds = round(sum(v.get("total_seconds") or 0 for v in found), 1) if found else None
            status = "Xong" if found else "Chưa"
        elif key:
            status = "Xong" if key in rep else "Chưa"
            seconds = rep.get(key, {}).get("total_seconds")
        elif step == "01":
            status = "Xong" if ov.get("hdfs", {}).get("raw", {}).get("files") else "Chưa"
        elif step == "07":
            status = "Xong" if ov.get("exported_at") else "Chưa"
        elif step == "08":
            status = "Đang làm"
        else:
            # buoc 10: Xong khi da co ket qua kiem tra (stream_report, 10c); Dang lam khi luong da ghi trending
            status = "Xong" if "stream_report" in rep else ("Đang làm" if n_trending else "Chưa")
        out.append({"step": step, "name": name, "status": status, "seconds": seconds})
    return out


@cached
def overview_doc():
    return get_db().overview.find_one({"_id": "overview"}, {"_id": 0}) or {}


@router.get("/overview", summary="E1 – số liệu tổng quan và tiến độ pipeline")
def overview():
    ov = dict(overview_doc())
    hdfs = ov.get("hdfs", {})
    ov["hdfs_total"] = {"bytes": sum(v["bytes"] for v in hdfs.values()),
                        "bytes_with_replicas": sum(v["bytes_with_replicas"] for v in hdfs.values())}
    ov["pipeline"] = pipeline(ov)
    return ov


@cached
def filter_values():
    db = get_db()
    meals = set(db.dishes.distinct("meal_types"))
    return {"categories": categories(), "meal_types": [m for m in MEALS if m in meals],
            "dish_types": sorted(x for x in db.dishes.distinct("dish_type_fixed") if x),
            "regions": [r for r in ("Bắc", "Trung", "Nam") if r in set(db.users.distinct("region"))],
            "age_groups": sorted(x for x in db.users.distinct("age_group") if x)}


@router.get("/meta/filters", summary="E22 – giá trị cho bộ lọc (nhóm món, bữa, vùng, tuổi)")
def meta_filters():
    return filter_values()
