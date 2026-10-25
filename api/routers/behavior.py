"""E2 heatmap gio x thu, E3 theo thang, E6 pheu chuyen doi (bang buoc 05)."""
from typing import Literal

from fastapi import APIRouter

from ..cache import cached
from ..db import get_db
from .overview import reports

router = APIRouter(prefix="/behavior", tags=["Hành vi ăn uống"])


@cached
def table(name, sort=None):
    cur = get_db()[f"analysis_{name}"].find({}, {"_id": 0})
    if sort:
        cur = cur.sort(list(sort))
    return list(cur)


@router.get("/heatmap", summary="E2 – heatmap giờ × thứ (168 ô)")
def heatmap(metric: Literal["cooks", "views", "events"] = "cooks"):
    rows = table("heatmap_hour_dow", (("dow_idx", 1), ("hour", 1)))
    cells = [{"dow_idx": r["dow_idx"], "dow_vn": r["dow_vn"], "hour": r["hour"], "value": r[metric]} for r in rows]
    top = sorted(cells, key=lambda c: -c["value"])[:5]
    return {"metric": metric, "cells": cells, "top": top}


@router.get("/monthly", summary="E3 – lượt nấu theo tháng, nhóm món theo tháng, mùa")
def monthly(region: Literal["Tất cả", "Bắc", "Trung", "Nam"] = "Tất cả"):
    by_cat = table("trend_month_category", (("month", 1), ("dish_category", 1)))
    season_all = table("season_month", (("region", 1), ("month", 1)))
    views = reports().get("model_split_report", {}).get("views", {})
    val_m = views.get("val", {}).get("eval_month")
    test_m = views.get("test", {}).get("eval_month")
    tet = {r["month"]: r["share_pct"] for r in season_all if r["region"] == "Tất cả" and r["season"] == "tết"}
    months = {}
    for r in by_cat:
        m = months.setdefault(r["month"], {"month": r["month"], "cooks": 0, "views": 0})
        m["cooks"] += r["cooks"]
        m["views"] += r["views"]
    out = []
    for k in sorted(months):
        m = months[k]
        m["split"] = "val" if k == val_m else "test" if k == test_m else "train"
        m["tet_share_pct"] = tet.get(k)
        out.append(m)
    tet_month = max(tet, key=tet.get) if tet else None
    return {"months": out, "tet_month": tet_month, "val_month": val_m, "test_month": test_m,
            "by_category": [{k: r[k] for k in ("month", "dish_category", "cooks", "cook_share_pct")} for r in by_cat],
            "season": [{k: r[k] for k in ("month", "season", "cooks", "share_pct")}
                       for r in season_all if r["region"] == region]}


@router.get("/funnel", summary="E6 – phễu chuyển đổi theo cặp user–món và theo nhóm món")
def funnel():
    rows = table("funnel_by_category")
    allr = next((r for r in rows if r["dish_category"] == "Tất cả"), {})
    pairs = {k: allr.get(f"{k}_pairs") for k in ("view", "favorite", "cook", "rate")}
    return {"pairs": pairs,
            "rates": {k: allr.get(k) for k in ("favorite_per_view_pct", "cook_per_view_pct", "rate_per_cook_pct",
                                              "avg_rating")},
            "users": reports().get("analysis_report", {}).get("funnel_users"),
            "by_category": [r for r in rows if r["dish_category"] != "Tất cả"]}
