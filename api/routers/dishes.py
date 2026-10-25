"""E8 tong quan danh muc, E10 nguyen lieu pho bien, E11 do thi nguyen lieu, E12 tim mon, E13 chi tiet mon,
E14 danh sach mon theo bo loc (xep theo stats.cook_rank)."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..cache import cached
from ..db import get_db
from ..dishes_common import CARD_PROJ, DishFilter, card, cards, dish_filter
from ..schemas import DishCard, DishDetail, DishList
from ..text import normalize_query, search_regex
from .behavior import table
from .overview import reports

router = APIRouter(prefix="/dishes", tags=["Món ăn"])
ing_router = APIRouter(prefix="/ingredients", tags=["Món ăn"])


@cached
def catalog_facets():
    """Aggregation $facet tren dishes: dem theo loai mon va 3 co (chay, nhanh, cay)."""
    flag = lambda f: [{"$match": {f: True}}, {"$count": "n"}]  # noqa: E731
    res = next(get_db().dishes.aggregate([{"$facet": {
        "total": [{"$count": "n"}],
        "veg": flag("is_vegetarian"), "quick": flag("is_quick"), "spicy": flag("is_spicy"),
        "by_type": [{"$group": {"_id": "$dish_type_fixed", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}],
        "by_source": [{"$group": {"_id": "$source", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}],
    }}]))
    one = lambda k: res[k][0]["n"] if res[k] else 0  # noqa: E731
    return {"n": one("total"), "veg": one("veg"), "quick": one("quick"), "spicy": one("spicy"),
            "by_type": [{"value": r["_id"], "n_dishes": r["n"]} for r in res["by_type"]],
            "by_source": [{"value": r["_id"], "n_dishes": r["n"]} for r in res["by_source"]]}


@router.get("/summary", summary="E8 – danh mục món: số món, tỷ lệ chay/nhanh/cay, danh mục so với lượt nấu, đuôi dài")
def summary():
    f = catalog_facets()
    n = f["n"] or 1
    rep = reports().get("analysis_report", {})
    cvc = {}
    for r in table("catalog_vs_cooked"):
        cvc.setdefault(r["attribute"], []).append({k: r[k] for k in ("value", "n_dishes", "cooks", "catalog_pct",
                                                                    "cook_pct", "cooks_per_dish", "lift")})
    for v in cvc.values():
        v.sort(key=lambda r: -r["catalog_pct"])
    return {"kpi": {"n_dishes": f["n"], "veg_pct": round(100 * f["veg"] / n, 2), "quick_pct": round(100 * f["quick"] / n, 2),
                    "spicy_pct": round(100 * f["spicy"] / n, 2), "n_ingredients": rep.get("n_distinct_ingredients")},
            "by_type": f["by_type"], "by_source": f["by_source"],
            "catalog_vs_cooked": cvc,
            "long_tail": {"curve": table("long_tail_curve", (("dish_pct", 1),)), **(rep.get("long_tail") or {})}}

DETAIL_FIELDS = ["ingredient_list", "ingredients", "preparation", "cooking_method", "serving_size", "source",
                 "season", "main_protein", "main_method", "stats", "companions"]


@router.get("", response_model=DishList, summary="E14 – danh sách món theo bộ lọc, xếp theo lượt nấu")
def list_dishes(f: DishFilter = Depends(dish_filter), skip: int = Query(0, ge=0, le=6000),
                limit: int = Query(24, ge=1, le=48)):
    db = get_db()
    q = f.query()
    cur = (db.dishes.find(q, {**CARD_PROJ, "stats.cook_rank": 1, "stats.cooks": 1})
           .sort("stats.cook_rank", 1).skip(skip).limit(limit))
    items = []
    for d in cur:
        c = card(d)
        c["cook_rank"], c["cooks"] = d["stats"].get("cook_rank"), d["stats"].get("cooks")
        items.append(c)
    return {"total": db.dishes.count_documents(q), "items": items}


@router.get("/search", response_model=list[DishCard], summary="E12 – tìm món theo tên (có dấu hay không dấu đều được)")
def search(q: str = Query(..., min_length=2, max_length=60), limit: int = Query(20, ge=1, le=30)):
    if not normalize_query(q):
        return []
    cur = (get_db().dishes.find({"name_search": {"$regex": search_regex(q)}}, CARD_PROJ)
           .sort("stats.cook_rank", 1).limit(limit))
    return [card(d) for d in cur]


@ing_router.get("/top", summary="E10 – nguyên liệu có trong các món được nấu nhiều nhất")
def top_ingredients(limit: int = Query(20, ge=1, le=50), seasoning: bool = Query(False, description="tính cả gia vị")):
    q = {} if seasoning else {"is_seasoning": False}
    cur = (get_db().analysis_top_ingredients.find(q, {"_id": 0}).sort("cook_rank", 1).limit(limit))
    return [{**r, "rank": i + 1} for i, r in enumerate(cur)]


@ing_router.get("/graph", summary="E11 – đồ thị nguyên liệu hay đi cùng nhau (FP-Growth, cạnh xếp theo lift)")
def ingredient_graph(variant: Literal["bỏ gia vị", "giữ gia vị"] = "bỏ gia vị", limit: int = Query(80, ge=1, le=150)):
    edges = list(get_db().ingredient_edges.find({"variant": variant}, {"_id": 0, "variant": 0})
                 .sort("lift", -1).limit(limit))
    deg = {}
    for e in edges:
        for k in ("src", "dst"):
            deg[e[k]] = deg.get(e[k], 0) + 1
    nodes = [{"name": k, "degree": v} for k, v in sorted(deg.items(), key=lambda x: (-x[1], x[0]))]
    return {"variant": variant, "nodes": nodes, "edges": edges}


@router.get("/{food_id}", response_model=DishDetail, summary="E13 – chi tiết món, món tương tự, món ăn kèm")
def detail(food_id: int, n_similar: int = Query(8, ge=0, le=12)):
    db = get_db()
    d = db.dishes.find_one({"_id": food_id}, {**CARD_PROJ, **{k: 1 for k in DETAIL_FIELDS}})
    if not d:
        raise HTTPException(404, f"Không tìm thấy món {food_id}")
    out = card(d)
    out.update({k: d.get(k) for k in DETAIL_FIELDS if k != "companions"})
    out["ingredient_list"] = out["ingredient_list"] or []
    cs = cards()
    out["companions"] = [{**cs[c["food_id"]], "confidence": c["confidence"], "lift": c["lift"]}
                         for c in d.get("companions") or [] if c["food_id"] in cs]
    sim = db.similar.find_one({"_id": food_id}, {"items": {"$slice": n_similar}}) if n_similar else None
    out["similar"] = [{**cs[s["food_id"]], "sim": s["sim"]} for s in (sim or {}).get("items", []) if s["food_id"] in cs]
    return out
