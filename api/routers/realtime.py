"""E25 mon thinh hanh theo cua so thoi gian (Structured Streaming, D18).

Doc trending (1 doc / cua so 60 phut truot 15 phut x pham vi: toan quoc, 3 vung) va stream_status (heartbeat,
dong ho mo phong, watermark, do tre). Khong cache: trang goi lai moi 5 giay.
  - "1 gio qua" = cua so gan nhat co window_end <= sim_now (gio cua su kien moi nhat da xu ly, khong vuot moc
    ket thuc cua doan phat lai, vi tick cuoi co ts = ket thuc + 75 phut).
  - Cua so co window_end > sim_now dang dien ra -> in_progress ("dang cap nhat").
  - final = window_end <= watermark: Spark da chot, su kien den tre hon se bi bo.
  - "Tang nhanh" so [t-60, t) voi [t-120, t-60) (hai cua so khong chong nhau), luong tinh san (prev_cooks).
Trang thai: "đang chạy" khi heartbeat moi hon 30 giay; "đã dừng" khi con du lieu ma khong con heartbeat;
"chưa chạy" khi trong.
Series: luong dang chay -> `windows` cua so gan nhat; da dung -> ca doan phat lai (bo qua `windows`).
Luoi cua so 15 phut lien tuc; cua so khong co doc trong trending (khong co su kien nao duoc dem) ghi 0.
stream.replay_end / at_end: moc ket thuc doan phat lai (vd 24:00 = 00:00 ngay sau) va gio mo phong da cham moc do chua.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Query

from ..db import get_db
from ..dishes_common import cards

router = APIRouter(tags=["Thời gian thực"])
VN = timezone(timedelta(hours=7))
SCOPES = ["all", "Bắc", "Trung", "Nam"]
HEARTBEAT_S = 30
STATUS_KEYS = ["state", "run_id", "replay", "trigger_s", "input_rows", "input_rows_per_s", "processed_rows_per_s",
               "batch_ms", "latency_s", "dropped_by_watermark", "state_rows", "n_batches"]


def vn(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(VN).isoformat(timespec="seconds") if dt else None


def empty(scope):
    return {"status": "chưa chạy", "stream": None, "scope": scope, "scopes": SCOPES, "current": None,
            "in_progress": [], "series": {"windows": [], **{s: [] for s in SCOPES}}, "updated_at": None}


@router.get("/trending", summary="E25 – món thịnh hành theo cửa sổ thời gian (Structured Streaming)")
def trending(scope: Literal["all", "Bắc", "Trung", "Nam"] = "all",
             limit: int = Query(10, ge=1, le=20), windows: int = Query(16, ge=1, le=48)):
    db = get_db()
    st = db.stream_status.find_one({"_id": "current"}) or {}
    if not st and not db.trending.estimated_document_count():
        return empty(scope)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age = (now - st["updated_at"]).total_seconds() if st.get("updated_at") else None
    status = "đang chạy" if st.get("state") == "đang chạy" and age is not None and age < HEARTBEAT_S else "đã dừng"
    sim_now, wm = st.get("sim_now"), st.get("watermark")
    rp = st.get("replay") or {}
    end = None
    if rp.get("day") and rp.get("to"):
        h, m = (int(x) for x in rp["to"].split(":"))
        end = (datetime.fromisoformat(rp["day"]) + timedelta(days=rp.get("days", 1) - 1, hours=h, minutes=m)
               - timedelta(hours=7))                                      # gio VN -> UTC khong mui gio (nhu pymongo)
    if sim_now is not None and end is not None:
        # tick cuoi (gio ket thuc + 75 phut) day max(ts) vuot qua doan phat lai: gio mo phong khong qua moc ket thuc
        sim_now = min(sim_now, end)
    if sim_now is None:
        last = db.trending.find_one({}, {"window_end": 1}, sort=[("window_end", -1)])
        sim_now = last["window_end"] if last else None
    if sim_now is None:
        return {**empty(scope), "status": status}

    proj = {"_id": 0, "window_start": 1, "window_end": 1, "scope": 1, "meal_slot": 1, "total_cooks": 1,
            "total_views": 1, "n_dishes": 1, "items": 1, "rising": 1, "batch_id": 1, "updated_at": 1}
    live = status == "đang chạy"
    done = list(db.trending.find({"window_end": {"$lte": sim_now}}, {"_id": 0, "window_end": 1, "scope": 1, "total_cooks": 1})
                .sort("window_end", -1).limit(windows * len(SCOPES) if live else 0))
    ends = sorted({d["window_end"] for d in done})
    if ends:
        # luoi 15 phut lien tuc: cua so khong co doc nao (khong co su kien duoc dem, vd 14-16h) = 0 luot nau
        step = timedelta(minutes=15)
        ends = [ends[0] + i * step for i in range(int((ends[-1] - ends[0]) / step) + 1)]
    if live:
        ends = ends[-windows:]
    tot = {(d["window_end"], d["scope"]): d["total_cooks"] for d in done}
    series = {"windows": [vn(e) for e in ends], **{s: [tot.get((e, s), 0) for e in ends] for s in SCOPES}}

    cs = cards()
    cur = db.trending.find_one({"scope": scope, "window_end": {"$lte": sim_now}}, proj, sort=[("window_end", -1)])
    current = None
    if cur:
        current = {
            "window_start": vn(cur["window_start"]), "window_end": vn(cur["window_end"]),
            "meal_slot": cur.get("meal_slot"), "total_cooks": cur["total_cooks"], "total_views": cur["total_views"],
            "n_dishes": cur["n_dishes"], "final": bool(wm and cur["window_end"] <= wm),
            "batch_id": cur.get("batch_id"), "written_at": vn(cur.get("updated_at")),
            "items": [{**cs[i["food_id"]], **{k: i[k] for k in ("cooks", "views", "favorites", "rank", "prev_cooks")},
                       "delta": i["cooks"] - i["prev_cooks"]}
                      for i in cur.get("items", [])[:limit] if i["food_id"] in cs],
            "rising": [{**cs[i["food_id"]], **{k: i[k] for k in ("cooks", "prev_cooks", "delta")}}
                       for i in cur.get("rising", []) if i["food_id"] in cs],
        }
    in_prog = [{"window_start": vn(d["window_start"]), "window_end": vn(d["window_end"]),
                "total_cooks": d["total_cooks"], "top": cs.get(d["items"][0]["food_id"], {}).get("dish_name")
                if d.get("items") else None}
               for d in db.trending.find({"scope": scope, "window_end": {"$gt": sim_now}},
                                         {"_id": 0, "window_start": 1, "window_end": 1, "total_cooks": 1,
                                          "items": {"$slice": 1}}).sort("window_end", 1)]
    stream = {k: st.get(k) for k in STATUS_KEYS}
    stream.update({"batch_id": st.get("last_batch_id"), "data_batch_id": st.get("data_batch_id"),
                   "newest_emit": vn(st.get("newest_emit")),
                   "sim_now": vn(sim_now), "watermark": vn(wm), "replay_end": vn(end),
                   "at_end": bool(end is not None and sim_now >= end), "started_at": vn(st.get("started_at")),
                   "updated_at": vn(st.get("updated_at")), "heartbeat_age_s": round(age, 1) if age is not None else None})
    return {"status": status, "stream": stream, "scope": scope, "scopes": SCOPES, "current": current,
            "in_progress": in_prog, "series": series, "updated_at": vn(st.get("updated_at"))}
