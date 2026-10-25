"""E17 user mau, E18 ho so user, E19 goi y cho user co san, E20 goi y cho user moi.

E18, E19, E20 khong bao gio tra truth (persona that): projection {truth: 0} va schema khong co truong nay.
Chi E17 co persona (chon user mau theo persona), kem verify_only = true (D15 chinh sua b).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from .. import reasons
from ..cache import cached
from ..db import get_db
from ..dishes_common import CARD_PROJ, DishFilter, card, cards, check_category, dish_filter
from ..schemas import DemoUsersOut, NewUserIn, RecsOut, UserOut

router = APIRouter(tags=["Gợi ý món"])

GROUPS = ["ấm", "ít", "lạnh"]
DEMO_PER_GROUP, DEMO_PER_PERSONA = 3, 2
DEMO_PROJ = {"group": 1, "region": 1, "age_group": 1, "profile.n_cook": 1}


def demo_user(u):
    return {"user_id": u["_id"], "group": u.get("group"), "region": u.get("region"),
            "age_group": u.get("age_group"), "n_cook": (u.get("profile") or {}).get("n_cook")}


@cached
def demo_users():
    """User mau co dinh: user_id nho nhat trong moi nhom (co >= 3 mon trong history, tru nhom lanh)."""
    db = get_db()
    by_group = {}
    for g in GROUPS:
        q = {"group": g} if g == "lạnh" else {"group": g, "history.2": {"$exists": True}}
        by_group[g] = [demo_user(u) for u in db.users.find(q, DEMO_PROJ).sort("_id", 1).limit(DEMO_PER_GROUP)]
    by_persona = []
    for p in sorted(x for x in db.users.distinct("truth.persona_main") if x):
        q = {"truth.persona_main": p, "group": "ấm", "history.2": {"$exists": True}}
        us = [demo_user(u) for u in db.users.find(q, DEMO_PROJ).sort("_id", 1).limit(DEMO_PER_PERSONA)]
        by_persona.append({"persona": p, "verify_only": True, "users": us})
    return {"by_group": by_group, "by_persona": by_persona, "verify_only": True}


@router.get("/users/demo", response_model=DemoUsersOut,
            summary="E17 – user mẫu theo nhóm ấm/ít/lạnh và theo persona (persona chỉ để kiểm chứng)")
def users_demo():
    return demo_users()


@router.get("/users/{user_id}", response_model=UserOut, summary="E18 – hồ sơ người dùng (không có persona thật)")
def user(user_id: int):
    u = get_db().users.find_one({"_id": user_id}, {"truth": 0})
    if not u:
        raise HTTPException(404, f"Không tìm thấy người dùng {user_id}")
    cs = cards()
    hist = [{**cs[h["food_id"]], "n_cook": h["n_cook"], "last_cook": h.get("last_cook")}
            for h in u.get("history") or [] if h["food_id"] in cs]
    return {"user_id": u["_id"], "region": u.get("region"), "age_group": u.get("age_group"),
            "gender": u.get("gender"), "group": u.get("group"), "cluster_k8": u.get("cluster_k8"),
            "profile": u.get("profile"), "history": hist, "n_test_cooks": len(u.get("test_cooks") or [])}


def fill_items(db, f, exclude, n):
    """Mon bu (D14 d): cung bo loc, bo cac mon da co, xep theo stats.cook_rank toan danh muc."""
    q = {**f.query(), "_id": {"$nin": list(exclude)}}
    return list(db.dishes.find(q, CARD_PROJ).sort("stats.cook_rank", 1).limit(n))


@router.get("/recs/{user_id}", response_model=RecsOut, summary="E19 – gợi ý cho người dùng có sẵn, có bộ lọc")
def recs_for_user(user_id: int, f: DishFilter = Depends(dish_filter), limit: int = Query(10, ge=1, le=20)):
    db = get_db()
    rec = db.recs.find_one({"_id": user_id})
    if not rec:
        raise HTTPException(404, f"Không tìm thấy người dùng {user_id}")
    u = db.users.find_one({"_id": user_id}, {"region": 1, "age_group": 1, "test_cooks": 1, "history": 1}) or {}
    test_cooks = set(u.get("test_cooks") or [])
    n_hist = {h["food_id"]: h["n_cook"] for h in u.get("history") or []}
    items = rec["items"]
    ids = [x["food_id"] for x in items]
    found = {d["_id"]: d for d in db.dishes.find({"_id": {"$in": ids}, **f.query()}, CARD_PROJ)}
    names = cards()
    out = []
    for x in items:
        if len(out) >= limit:
            break
        d = found.get(x["food_id"])
        if d is None:
            continue
        src, because = x["source"], None
        if src == "content_slot":
            b = x.get("because_food_id")
            bname = names.get(b, {}).get("dish_name") if b is not None else None
            because = {"food_id": b, "dish_name": bname} if b is not None else None
            reason = reasons.content_reason(bname, x.get("because_cooked", False))
        elif src == "pop":
            reason = reasons.pop_reason(u.get("region"), u.get("age_group"))
        elif src == "rep":
            reason = reasons.rep_reason(n_hist.get(x["food_id"]))
        else:
            reason = reasons.ALS
        out.append({**card(d), "rank": len(out) + 1, "rec_rank": x["rank"], "source": src,
                    "dot": reasons.DOT.get(src, "herb"), "reason": reason, "because": because,
                    "hit": x["food_id"] in test_cooks})
    n_recs = len(out)
    if n_recs < limit:
        reason = reasons.fill_reason(f.label())
        for d in fill_items(db, f, set(ids) | set(n_hist), limit - n_recs):
            out.append({**card(d), "rank": len(out) + 1, "rec_rank": None, "source": "fill", "dot": "neutral",
                        "reason": reason, "because": None, "hit": d["_id"] in test_cooks})
    return {"user_id": user_id, "filters": f.as_dict(), "items": out,
            "summary": {"from_recs": n_recs, "from_fill": len(out) - n_recs,
                        "hits": sum(1 for x in out if x["hit"]), "n_test_cooks": len(test_cooks)}}


@router.post("/recs/new-user", response_model=RecsOut,
             summary="E20 – gợi ý cho người dùng mới từ các món đã chọn (content), bù bằng món phổ biến")
def recs_new_user(body: NewUserIn):
    check_category(body.category)
    f = DishFilter(body.veg, body.quick, body.not_spicy, body.meal, body.category)
    db = get_db()
    cs = cards()
    chosen = list(dict.fromkeys(body.food_ids))
    missing = [i for i in chosen if i not in cs]
    if missing:
        raise HTTPException(404, f"Không tìm thấy món {', '.join(map(str, missing))}")
    # Cong sim tu similar cua cac mon da chon; moi ung vien nho mon da chon giong no nhat lam ly do
    score, best = {}, {}
    for doc in db.similar.find({"_id": {"$in": chosen}}):
        for s in doc["items"]:
            j = s["food_id"]
            if j in chosen:
                continue
            score[j] = score.get(j, 0.0) + s["sim"]
            if s["sim"] > best.get(j, (None, -1.0))[1]:
                best[j] = (doc["_id"], s["sim"])
    cand = sorted(score, key=lambda j: (-score[j], j))
    found = {d["_id"]: d for d in db.dishes.find({"_id": {"$in": cand}, **f.query()}, CARD_PROJ)}
    out = []
    for j in cand:
        if len(out) >= body.limit:
            break
        if j in found:
            b = best[j][0]
            out.append({**card(found[j]), "rank": len(out) + 1, "rec_rank": None, "source": "content",
                        "dot": "chili", "reason": f"Giống món {cs[b]['dish_name']} bạn đã chọn",
                        "because": {"food_id": b, "dish_name": cs[b]["dish_name"]}, "hit": None})
    n_content = len(out)
    # Bu 1: popular (vung-tuoi neu co du vung va tuoi, khong thi "chung"), loc lai bang F trong RAM
    key = f"vùng-tuổi|{body.region}|{body.age_group}" if body.region and body.age_group else "chung"
    pop = db.popular.find_one({"_id": key}) or {"items": []}
    used = set(chosen) | {x["food_id"] for x in out}
    reason = reasons.pop_reason(body.region, body.age_group) if key != "chung" else "Đang được nhiều người nấu"
    for p in pop["items"]:
        if len(out) >= body.limit:
            break
        c = cs.get(p["food_id"])
        if c and p["food_id"] not in used and f.match(c):
            used.add(p["food_id"])
            out.append({**c, "rank": len(out) + 1, "rec_rank": None,
                        "source": "pop", "dot": "neutral", "reason": reason, "because": None, "hit": None})
    n_pop = len(out) - n_content
    # Bu 2: popular chi co 100 mon -> con thieu thi bu tu danh muc (giong E19)
    if len(out) < body.limit:
        reason = reasons.fill_reason(f.label())
        for d in fill_items(db, f, used, body.limit - len(out)):
            out.append({**card(d), "rank": len(out) + 1, "rec_rank": None, "source": "fill", "dot": "neutral",
                        "reason": reason, "because": None, "hit": None})
    return {"user_id": None, "filters": {**f.as_dict(), "food_ids": chosen, "region": body.region,
                                         "age_group": body.age_group},
            "items": out, "summary": {"from_recs": n_content, "from_popular": n_pop,
                                      "from_fill": len(out) - n_content - n_pop}}
