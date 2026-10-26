"""E23 so sanh mo hinh xep hang, E24 chi tiet danh gia (tu cac report + collection perf), E26 report nguyen ban."""
from typing import Literal

from fastapi import APIRouter, HTTPException

from ..cache import cached
from ..db import get_db
from ..labels import model_kind, model_label
from .overview import reports

router = APIRouter(tags=["Đánh giá mô hình"])

STEP_OF_REPORT = {
    "simulate_report": "04 Sinh hành vi", "analysis_report": "05 Phân tích hành vi",
    "model_split_report": "06a Chia dữ liệu", "model_als_report": "06b ALS + baseline",
    "model_content_report": "06c Content + LSH", "model_fpgrowth_report": "06d FP-Growth",
    "model_kmeans_report": "06e K-means", "model_hybrid_report": "06f Hybrid", "model_control_report": "06g Đối chứng",
}


COLD_SOURCE_MODEL = {"als": "als_implicit", "content": "content", "rep": "nau_lai", "hybrid": "hybrid",
                     "hybrid_c2": "hybrid_c2"}


@cached
def metric_rows(view, variant, group):
    return list(get_db().metrics.find({"view": view, "variant": variant, "group": group}, {"_id": 0}))


@cached
def perf_docs():
    return list(get_db().perf.find())


PERF_ROW_KEYS = ("job", "step", "level", "level_pct", "workers", "n_runs", "n_ok", "median_s", "min_s", "max_s",
                 "runs_s", "events_per_s", "timings_s")
PERF_SPARK_KEYS = ("shuffle_read_mb", "shuffle_remote_read_mb", "shuffle_write_mb", "spill_memory_mb", "spill_disk_mb",
                   "gc_s", "executor_run_s", "cpu_ratio", "tasks", "stages")


def perf_block():
    """Do hieu nang Spark (D17): thoi gian theo job x muc du lieu x so worker, speedup (theo job, theo muc), tong chuoi theo muc."""
    docs = perf_docs()
    summary = next((d for d in docs if d["_id"] == "summary"), None)
    if not summary:
        return {"available": False}
    rows = []
    for d in docs:
        if d.get("kind") != "job":
            continue
        row = {k: d.get(k) for k in PERF_ROW_KEYS}
        row["failed"] = len(d.get("failed") or [])
        row["spark"] = {k: (d.get("spark") or {}).get(k) for k in PERF_SPARK_KEYS}
        rows.append(row)
    return {"available": True, "rows": rows,
            **{k: summary.get(k) for k in ("speedup", "speedup_by_scale", "chain_totals", "scaling_2w", "cluster", "data", "notes",
                                           "runs_total", "runs_failed", "generated_at")}}


@router.get("/eval/ranking", summary="E23 – độ đo xếp hạng các mô hình, khoảng tin cậy 95%")
def ranking(view: Literal["test", "val"] = "test",
            variant: Literal["chính", "khám phá", "ngoài độ chính xác"] = "chính",
            group: Literal["tất cả", "ấm", "ít", "lạnh"] = "tất cả"):
    rows = [{"model": r["model"], "label": model_label(r["model"]), "kind": model_kind(r["model"]),
             "metrics": r["metrics"]} for r in metric_rows(view, variant, group)]
    ci = []
    if view == "test" and variant == "chính":
        for c in reports().get("models_metrics", {}).get("ci95_test_ndcg@10", []):
            if c.get("users") == group:
                a, b = [s.strip() for s in c["so_sanh"].split(" - ")]
                ci.append({"so_sanh": c["so_sanh"], "label": f"{model_label(a)} − {model_label(b)}",
                           "metric": c["metric"], "n_users": c["n_users"], "hieu": c["hieu"], "ci95": c["ci95"]})
    return {"view": view, "variant": variant, "group": group, "rows": rows, "ci95": ci}


@router.get("/eval/details", summary="E24 – RMSE, dò tham số ALS, LSH, FP-Growth, đối chứng, K-means, thời gian, hiệu năng Spark")
def details():
    rep = reports()
    als = rep.get("model_als_report", {})
    rating = als.get("test", {}).get("rating", {})
    ctrl = rep.get("model_control_report", {})
    hyb = rep.get("model_hybrid_report", {})
    km = rep.get("model_kmeans_report", {})
    fp = rep.get("model_fpgrowth_report", {}).get("meal_eval_hit_rate@3", {})
    labels = {"trung_binh": "Trung bình chung", "bias": "Baseline bias", "als_explicit": "ALS explicit"}
    return {
        "rmse": {"n": rating.get("rows_common"),
                 "rows": [{"model": k, "label": labels.get(k, k), **v}
                          for k, v in rating.get("on_common_rows", {}).items()]},
        "als_grid": als.get("tuning_als_implicit", []),
        "als_best": als.get("best_als_implicit"),
        "hybrid_weights": hyb.get("best_weights"),
        # Thi nghiem mon moi (an 300 mon khoi train): recall@10 tren cac cap test co mon bi an
        # (khoa trong report la ten nguon cua hybrid -> doi sang ten mo hinh trong metrics)
        "new_item_recall": {COLD_SOURCE_MODEL[k]: v.get("hidden_recall@10") for k, v in
                            hyb.get("cold_items", {}).get("by_source", {}).items() if k in COLD_SOURCE_MODEL},
        "lsh": rep.get("model_content_report", {}).get("minhash", []),
        "fpgrowth_hit": [{"label": "Luật FP-Growth", "value": fp.get("luat_fpgrowth")},
                         {"label": "Mốc theo nhóm món", "value": fp.get("moc_theo_nhom_mon")},
                         {"label": "Mốc 3 canh phổ biến", "value": fp.get("moc_3_canh_pho_bien")}],
        "control_06g": {
            "goc": [{"label": labels.get(k, k), **ctrl.get("test_common_rows", {}).get(k, {})}
                    for k in ("trung_binh", "bias", "als_explicit")],
            "mo_phong": [{"label": labels.get(k, k), **ctrl.get("simulated_for_comparison", {}).get(k, {})}
                         for k in ("trung_binh", "bias", "als_explicit")],
            "als_vs_mean_pct_goc": ctrl.get("als_vs_mean_improvement_pct_goc"),
            "als_vs_mean_pct_mo_phong": ctrl.get("simulated_for_comparison", {}).get("als_vs_mean_improvement_pct"),
            "rows": ctrl.get("rows"),
        },
        "kmeans_k": km.get("search", []),
        "timings": [{"report": k, "step": v, "seconds": rep[k].get("total_seconds")}
                    for k, v in STEP_OF_REPORT.items() if k in rep],
        "perf": perf_block(),
    }


@router.get("/reports/{name}", summary="E26 – nội dung một report (gỡ lỗi)")
def report(name: str):
    rep = reports()
    if name not in rep:
        raise HTTPException(404, f"Không có report {name}")
    return rep[name]
