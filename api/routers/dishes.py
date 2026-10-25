"""E12 tim mon, E13 chi tiet mon, E14 danh sach mon theo bo loc (xep theo stats.cook_rank)."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db
from ..dishes_common import CARD_PROJ, DishFilter, card, cards, dish_filter
from ..schemas import DishCard, DishDetail, DishList
from ..text import normalize_query, search_regex

router = APIRouter(prefix="/dishes", tags=["Món ăn"])

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
