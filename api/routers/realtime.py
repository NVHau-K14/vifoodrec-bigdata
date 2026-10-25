"""E25 mon thinh hanh theo cua so thoi gian (collection trending, do Structured Streaming ghi).

trending hien con rong -> status "chưa chạy". Schema document trending se chot khi thiet ke Structured Streaming;
tam doc dang {window_end, window_start?, items: [{food_id, cooks}]} va co the phai sua lai luc do.
"""
from fastapi import APIRouter, Query

from ..db import get_db
from ..dishes_common import cards

router = APIRouter(tags=["Thời gian thực"])


@router.get("/trending", summary="E25 – món thịnh hành theo cửa sổ thời gian (Structured Streaming)")
def trending(limit: int = Query(10, ge=1, le=20), windows: int = Query(12, ge=1, le=48)):
    docs = list(get_db().trending.find({}, {"_id": 0}).sort("window_end", -1).limit(windows))
    if not docs:
        return {"status": "chưa chạy", "updated_at": None, "windows": []}
    cs = cards()
    out = []
    for d in docs:
        items = [{**cs[i["food_id"]], "cooks": i.get("cooks")} for i in (d.get("items") or [])[:limit]
                 if i.get("food_id") in cs]
        out.append({"window_start": d.get("window_start"), "window_end": d.get("window_end"),
                    "total_cooks": d.get("total_cooks", sum(i.get("cooks") or 0 for i in d.get("items") or [])),
                    "items": items})
    return {"status": "đang chạy", "updated_at": docs[0].get("window_end"), "windows": out}
