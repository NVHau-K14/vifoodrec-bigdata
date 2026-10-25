"""E2 heatmap gio x thu, E3 theo thang, E4 mon theo bua, E5 lift theo nhom, E6 pheu, E7 thoi quen (bang buoc 05)."""
from typing import Literal

from fastapi import APIRouter, Query

from ..cache import cached
from ..db import get_db
from ..dishes_common import cards
from .overview import reports

SLOTS = ["sáng", "trưa", "tối", "khuya"]
# Thu tu hien thi cua cac nhom nguoi dung (hang cua heatmap lift)
GROUP_ORDER = {"region": ["Bắc", "Trung", "Nam"], "age_group": ["18-24", "25-34", "35-44", "45+"],
               "day_type": ["ngày thường", "cuối tuần"], "meal_slot": SLOTS}
BOOL_LABEL = {"is_quick": {"true": "món nhanh", "false": "không nhanh"},
              "is_spicy": {"true": "món cay", "false": "không cay"}}

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


@router.get("/top-dishes", summary="E4 – món nấu nhiều nhất hoặc đặc trưng (lift) theo bữa")
def top_dishes(slot: Literal["sáng", "trưa", "tối", "khuya"] = "tối", by: Literal["cooks", "lift"] = "cooks",
               limit: int = Query(10, ge=1, le=10)):
    # Bang chi giu hop cua top 10 theo luot nau (rk) va top 10 theo lift (rk_lift) moi bua -> limit <= 10
    key = "rk" if by == "cooks" else "rk_lift"
    rows = [r for r in table("top_dish_by_slot", (("meal_slot", 1), ("rk", 1))) if r["meal_slot"] == slot]
    rows = sorted((r for r in rows if r[key] <= limit), key=lambda r: r[key])
    cs = cards()
    out = []
    for r in rows:
        c = cs.get(r["food_id"]) or {"food_id": r["food_id"], "dish_name": r["dish_name"],
                                      "dish_category": r["dish_category"], "image_link": r.get("image_link")}
        out.append({**c, "rank": r[key], "cooks": r["cooks"], "share_pct": r["share_pct"], "lift": r["lift"]})
    return {"slot": slot, "by": by, "items": out}


@router.get("/lift", summary="E5 – lift của thuộc tính món theo nhóm người dùng (vùng, tuổi, ngày, bữa)")
def lift(group_type: Literal["region", "age_group", "day_type", "meal_slot"] = "region",
         attribute: Literal["dish_category", "main_protein", "main_method", "dish_type_fixed", "is_quick",
                            "is_spicy"] = "dish_category",
         min_cooks: int = Query(1000, ge=0, le=100000)):
    rows = [r for r in table("lift_by_group", (("group_type", 1), ("group_value", 1)))
            if r["group_type"] == group_type and r["attribute"] == attribute]
    order = GROUP_ORDER[group_type]
    groups = [g for g in order if any(r["group_value"] == g for r in rows)]
    # Cot xep theo ty trong chung (overall_pct) giam dan; o it hon min_cooks luot nau thi lift = null
    overall = {}
    for r in rows:
        overall[r["value"]] = r["overall_pct"]
    values = sorted(overall, key=lambda v: -overall[v])
    lab = BOOL_LABEL.get(attribute, {})
    cells = [{"group_value": r["group_value"], "value": r["value"], "value_label": lab.get(r["value"], r["value"]),
              "cooks": r["cooks"], "share_pct": r["share_pct"], "overall_pct": r["overall_pct"],
              "lift": r["lift"] if r["cooks"] >= min_cooks else None} for r in rows]
    return {"group_type": group_type, "attribute": attribute, "min_cooks": min_cooks, "groups": groups,
            "values": [{"value": v, "label": lab.get(v, v), "overall_pct": overall[v]} for v in values],
            "cells": cells}


@router.get("/habits", summary="E7 – thói quen nấu: số món mỗi phiên, nấu lại, lượt nấu mỗi user, điểm chấm")
def habits():
    session = table("session_size")
    slot_order = ["Tất cả"] + SLOTS
    session = sorted(session, key=lambda r: (slot_order.index(r["meal_slot"]) if r["meal_slot"] in slot_order else 9,
                                             r["size"]))
    repeat = sorted(table("repeat_by_category"), key=lambda r: (r["dish_category"] != "Tất cả", -r["repeat_pct"]))
    rep = reports().get("analysis_report", {})
    return {"session_size": session,
            "repeat_by_category": repeat,
            "user_activity": table("user_activity", (("ord", 1),)),
            "rating_dist": table("rating_dist", (("rating", 1),)),
            "rating": rep.get("rating"),
            "sessions_2plus_pct": rep.get("cook_sessions_2plus_dishes_pct")}


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
