"""Phan dung chung ve mon: projection the mon, bo loc F, cache the mon gon cua ca danh muc."""
from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import HTTPException, Query

from .cache import cached
from .db import get_db

MEALS = ["sáng", "trưa", "tối", "ăn vặt"]
Meal = Literal["sáng", "trưa", "tối", "ăn vặt"]

# The mon (DishCard): du de ve the o moi trang; khong co nutrition (so ngau nhien, D14)
CARD_FIELDS = ["dish_name", "image_link", "dish_category", "dish_type_fixed", "is_vegetarian", "is_quick",
               "is_spicy", "meal_types"]
CARD_PROJ = {k: 1 for k in CARD_FIELDS}


def card(doc):
    c = {"food_id": doc["_id"]}
    c.update({k: doc.get(k) for k in CARD_FIELDS})
    c["meal_types"] = c["meal_types"] or []
    return c


@cached
def cards():
    """{food_id: the mon + cook_rank, cooks} cua ca danh muc (5.499 mon, vai MB). Dung de tra ten va loc nhanh."""
    out = {}
    for d in get_db().dishes.find({}, {**CARD_PROJ, "stats.cook_rank": 1, "stats.cooks": 1}):
        c = card(d)
        st = d.get("stats") or {}
        c["cook_rank"], c["cooks"] = st.get("cook_rank"), st.get("cooks")
        out[d["_id"]] = c
    return out


@cached
def categories():
    return sorted(x for x in get_db().dishes.distinct("dish_category") if x)


@dataclass(frozen=True)
class DishFilter:
    veg: bool = False
    quick: bool = False
    not_spicy: bool = False
    meal: Optional[str] = None
    category: Optional[str] = None

    def query(self):
        q = {}
        if self.veg:
            q["is_vegetarian"] = True
        if self.quick:
            q["is_quick"] = True
        if self.not_spicy:
            q["is_spicy"] = False
        if self.meal:
            q["meal_types"] = self.meal
        if self.category:
            q["dish_category"] = self.category
        return q

    def match(self, c):
        """Loc the mon trong RAM (cung nghia voi query())."""
        return ((not self.veg or c["is_vegetarian"]) and (not self.quick or c["is_quick"])
                and (not self.not_spicy or c["is_spicy"] is False)
                and (not self.meal or self.meal in c["meal_types"])
                and (not self.category or c["dish_category"] == self.category))

    def label(self):
        """Mo ta bo loc cho cau ly do mon bu, vd "Món chay, món nhanh"; khong loc -> chuoi rong."""
        parts = []
        if self.veg:
            parts.append("món chay")
        if self.quick:
            parts.append("món nhanh")
        if self.not_spicy:
            parts.append("món không cay")
        if self.meal:
            parts.append("món ăn vặt" if self.meal == "ăn vặt" else f"bữa {self.meal}")
        if self.category:
            parts.append(self.category)
        if parts and not parts[0].startswith("món"):
            parts.insert(0, "món")
            parts = [" ".join(parts[:2])] + parts[2:]
        s = ", ".join(parts)
        return s[:1].upper() + s[1:]

    def as_dict(self):
        return {"veg": self.veg, "quick": self.quick, "not_spicy": self.not_spicy, "meal": self.meal,
                "category": self.category}


def check_category(category):
    if category is not None and category not in categories():
        raise HTTPException(422, f"Nhóm món không hợp lệ: {category}")


def dish_filter(veg: bool = Query(False, description="chỉ món chay"),
                quick: bool = Query(False, description="chỉ món nhanh (is_quick)"),
                not_spicy: bool = Query(False, description="bỏ món cay"),
                meal: Optional[Meal] = Query(None, description="bữa: sáng, trưa, tối, ăn vặt"),
                category: Optional[str] = Query(None, description="nhóm món (dish_category)")):
    check_category(category)
    return DishFilter(veg, quick, not_spicy, meal, category)
