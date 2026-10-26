"""
capture_screens.py - Chup anh giao dien cho bao cao bang Playwright (Chromium headless), ghi PNG vao docs/images/.

Nhom anh (--only, cach nhau dau phay; mac dinh: tat ca nhom tinh, KHONG gom realtime / sparkui / stopped):
  dashboard  7 trang dashboard o 1440 va 390 (toan trang)                       -> 08_<trang>_{1440,390}.png
  perfcard   the "Hieu nang Spark" o trang Danh gia                             -> 09_the_hieu_nang.png
  history    Spark History Server: danh sach app; Timeline + Executors cua 06b|s100|w1|r1 va w2|r1;
             Storage + SQL cua 05 (lan chay that)                              -> hs_*.png
  hdfs       HDFS UI: /data/curated, /data/events, /data/results/analysis, /data/stream -> hdfs_*.png
  mongo      mongo-express: database vifood, collection recs, trending         -> mongo_*.png
  realtime   trang Thoi gian thuc khi luong dang chay (1440, 390)               -> 08_thoi-gian-thuc_{1440,390}.png
  sparkui    Spark UI cua luong (:4041), tab Structured Streaming + thong ke    -> 10_spark_ui_*.png
  stopped    trang Thoi gian thuc khi luong da dung (1440)                      -> 10_thoi-gian-thuc_da-dung_1440.png
Anh 390: gia lap thiet bi di dong (viewport 390, is_mobile, has_touch), nhu lan chup 08_* bang DevTools Protocol.

An toan: truoc khi luu, kiem tra van ban cua trang khong chua mat khau trong .env; co thi bo anh va bao loi.
Danh sach anh (ten, noi dung, kich thuoc) ghi vao data/output/screenshots.json (gop voi lan chay truoc).

Chay tren may (can: pip install playwright && python -m playwright install chromium):
  python scripts/capture_screens.py --only dashboard,perfcard,history,hdfs,mongo
  python scripts/capture_screens.py --only realtime,sparkui      # khi luong dang chay
"""
import argparse
import json
import os
import re
import struct
import sys
import time
import urllib.request
from datetime import datetime

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
IMG = os.path.join(ROOT, "docs", "images")
MANIFEST = os.path.join(ROOT, "data", "output", "screenshots.json")
DASH = "http://localhost:8000"
PAGES = [("tong-quan", "index.html", "Tổng quan"), ("hanh-vi", "hanh-vi.html", "Hành vi ăn uống"),
         ("mon-an", "mon-an.html", "Món ăn"), ("phan-khuc", "phan-khuc.html", "Phân khúc người dùng"),
         ("goi-y", "goi-y.html", "Gợi ý món"), ("danh-gia", "danh-gia.html", "Đánh giá mô hình"),
         ("thoi-gian-thuc", "thoi-gian-thuc.html", "Thời gian thực")]
sys.stdout.reconfigure(encoding="utf-8")


def env_secrets():
    """Gia tri bi mat trong .env (mat khau, mat khau trong chuoi ket noi) de kiem tra anh khong lo."""
    out = set()
    with open(os.path.join(ROOT, ".env"), encoding="utf-8") as fh:
        for line in fh:
            k, _, v = line.strip().partition("=")
            if not v or k.startswith("#"):
                continue
            if "PASSWORD" in k:
                out.add(v)
            m = re.search(r"://[^:/@]+:([^@]+)@", v)
            if m:
                out.add(m.group(1))
    return {s for s in out if len(s) >= 4}


def env_value(key):
    with open(os.path.join(ROOT, ".env"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(key + "="):
                return line.strip().split("=", 1)[1]
    return None


SECRETS = env_secrets()
shots, problems = [], []


def png_size(path):
    with open(path, "rb") as fh:
        w, h = struct.unpack(">II", fh.read(24)[16:24])
    return w, h


def save(target, name, desc, full_page=True):
    """target: Page hoac Locator. Kiem tra bi mat roi chup."""
    page = target.page if hasattr(target, "page") and not hasattr(target, "goto") else target
    text = page.content() + page.url
    leaked = [s for s in SECRETS if s in text]
    if leaked:
        problems.append(f"{name}: trang chua gia tri bi mat trong .env, khong luu")
        print(f"[shot] BO {name}: lo bi mat", flush=True)
        return
    path = os.path.join(IMG, name)
    if hasattr(target, "goto"):
        target.screenshot(path=path, full_page=full_page)
    else:
        target.screenshot(path=path)
    w, h = png_size(path)
    shots.append({"file": f"docs/images/{name}", "desc": desc, "width": w, "height": h,
                  "kb": round(os.path.getsize(path) / 1024), "at": datetime.now().isoformat(timespec="seconds")})
    print(f"[shot] {name} {w}x{h} - {desc}", flush=True)


def settle(page, extra=1.5):
    """Doi tai xong: networkidle + khong con khung dang tai + them chut cho bieu do ve."""
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:  # noqa: BLE001
        pass
    try:
        page.wait_for_function("() => !document.querySelector('[data-state=\"loading\"]')", timeout=20000)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(extra)


def contexts(browser):
    desk = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1, locale="vi-VN")
    mob = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True,
                              has_touch=True, locale="vi-VN",
                              user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
                                         "Chrome/126.0 Mobile Safari/537.36")
    return desk, mob


def dashboard(browser, only_pages=None, prefix="08"):
    desk, mob = contexts(browser)
    for slug, url, title in PAGES:
        if only_pages and slug not in only_pages:
            continue
        for ctx, w in ((desk, 1440), (mob, 390)):
            p = ctx.new_page()
            p.goto(f"{DASH}/{url}")
            settle(p, 6 if slug in ("goi-y", "mon-an", "thoi-gian-thuc") else 3)   # anh mon: doi toi 4 giay roi thay
            save(p, f"{prefix}_{slug}_{w}.png", f"Dashboard, trang {title}, rộng {w}px (toàn trang)")
            p.close()
    desk.close(), mob.close()


def perfcard(browser):
    desk, mob = contexts(browser)
    p = desk.new_page()
    p.goto(f"{DASH}/danh-gia.html")
    settle(p, 3)
    card = p.locator("article.card", has=p.locator("h2", has_text="Hiệu năng Spark")).first
    card.scroll_into_view_if_needed()
    time.sleep(1.5)
    save(card, "09_the_hieu_nang.png", "Thẻ \"Hiệu năng Spark\" ở trang Đánh giá mô hình (1440px)")
    desk.close(), mob.close()


def hs_apps():
    with urllib.request.urlopen("http://localhost:18080/api/v1/applications?limit=1000", timeout=30) as r:
        return json.load(r)


def history(browser):
    apps = hs_apps()
    by_name = {}
    for a in apps:                                    # danh sach moi nhat truoc
        by_name.setdefault(a["name"], a)
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    ctx.set_default_navigation_timeout(180000)     # History Server doc event log lan dau co the lau
    p = ctx.new_page()
    p.goto("http://localhost:18080/")
    settle(p, 2)
    save(p, "hs_danh_sach_app.png", "Spark History Server: danh sách ứng dụng đã chạy", full_page=False)
    for w in (1, 2):
        name = f"06b_als|s100|w{w}|r1"
        a = by_name.get(name)
        if not a:
            problems.append(f"khong thay app {name} tren History Server")
            continue
        aid = a["id"]
        p.goto(f"http://localhost:18080/history/{aid}/jobs/")
        settle(p, 2)
        tl = p.locator("span.expand-application-timeline")
        if tl.count():
            tl.first.click()
            time.sleep(2.5)
        save(p, f"hs_06b_s100_w{w}_timeline.png",
             f"History Server: 06b ALS, 100% dữ liệu, {w} worker, lần 1 — Jobs + Event Timeline ({aid})")
        p.goto(f"http://localhost:18080/history/{aid}/executors/")
        settle(p, 2)
        save(p, f"hs_06b_s100_w{w}_executors.png",
             f"History Server: 06b ALS, 100% dữ liệu, {w} worker, lần 1 — Executors ({aid})")
    # 05 tren du lieu hien tai, 2 worker (lan 05 "that" tren cum chay truoc khi lam phang Zipf, D11)
    a05 = by_name.get("05_analysis|s100|w2|r1")
    if not a05:
        problems.append("khong thay app 05_analysis|s100|w2|r1 tren History Server")
    else:
        aid = a05["id"]
        p.goto(f"http://localhost:18080/history/{aid}/storage/")
        settle(p, 2)
        save(p, "hs_05_storage.png", f"History Server: 05 Phân tích hành vi (100%, 2 worker) — tab Storage ({aid})")
        p.goto(f"http://localhost:18080/history/{aid}/SQL/")
        settle(p, 2)
        save(p, "hs_05_sql.png", f"History Server: 05 Phân tích hành vi (100%, 2 worker) — tab SQL / DataFrame ({aid})")
    ctx.close()


def hdfs(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    p = ctx.new_page()
    for path, slug in [("/data/curated", "curated"), ("/data/events", "events"),
                       ("/data/results/analysis", "results_analysis"), ("/data/stream", "stream")]:
        p.goto(f"http://localhost:9870/explorer.html#{path}")
        p.wait_for_selector("#table-explorer tbody tr", timeout=20000)
        settle(p, 1.5)
        save(p, f"hdfs_{slug}.png", f"HDFS NameNode UI: thư mục {path}")
    ctx.close()


def mongo(browser):
    user, pw = env_value("ME_CONFIG_BASICAUTH_USERNAME"), env_value("ME_CONFIG_BASICAUTH_PASSWORD")
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1,
                              http_credentials={"username": user, "password": pw})
    p = ctx.new_page()
    p.goto("http://localhost:8090/db/vifood/")
    settle(p, 1.5)
    save(p, "mongo_vifood.png", "mongo-express: database vifood (danh sách collection, kích thước)")
    p.goto("http://localhost:8090/db/vifood/recs")
    settle(p, 1.5)
    save(p, "mongo_recs.png", "mongo-express: collection recs (1 doc / user, 50 món gợi ý)", full_page=False)
    p.goto("http://localhost:8090/db/vifood/trending")
    settle(p, 1.5)
    save(p, "mongo_trending.png", "mongo-express: collection trending (Structured Streaming)", full_page=False)
    ctx.close()


def realtime(browser, stopped=False):
    desk, mob = contexts(browser)
    targets = [(desk, 1440)] if stopped else [(desk, 1440), (mob, 390)]
    for ctx, w in targets:
        p = ctx.new_page()
        p.goto(f"{DASH}/thoi-gian-thuc.html")
        settle(p, 6)
        sim = p.locator(".kpi").nth(1).inner_text().replace("\n", " ")
        if stopped:
            save(p, f"10_thoi-gian-thuc_da-dung_{w}.png", f"Trang Thời gian thực khi luồng đã dừng ({sim}), rộng {w}px")
        else:
            save(p, f"08_thoi-gian-thuc_{w}.png", f"Trang Thời gian thực khi luồng đang chạy ({sim}), rộng {w}px")
        p.close()
    desk.close(), mob.close()


def sparkui(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    p = ctx.new_page()
    p.goto("http://localhost:4041/StreamingQuery/")
    settle(p, 1.5)
    save(p, "10_spark_ui_streaming.png", "Spark UI của luồng (:4041), tab Structured Streaming: query đang chạy")
    link = p.locator("table a[href*='statistics']").first
    if link.count():
        link.click()
        settle(p, 3)
        save(p, "10_spark_ui_streaming_stats.png",
             "Spark UI của luồng (:4041): thống kê query (tốc độ vào / xử lý, thời gian batch, state)")
    ctx.close()


def live05(browser):
    """Tab Storage cua 05 khi dang chay (:4040). History Server khong con bang cache vi 05 unpersist truoc khi ket thuc.
    Chay 05 vao goc do truoc (VIFOOD_DATA_ROOT=/perf/s100), roi goi nhom nay; doi toi khi co RDD trong cache."""
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:4040/api/v1/applications", timeout=5) as r:
                aid = json.load(r)[0]["id"]
            with urllib.request.urlopen(f"http://localhost:4040/api/v1/applications/{aid}/storage/rdd", timeout=5) as r:
                rdds = json.load(r)
            full = [x for x in rdds if x.get("numPartitions") and x.get("numCachedPartitions") == x["numPartitions"]]
            if full:                                   # co it nhat 1 bang da cache du 100%
                break
        except Exception:  # noqa: BLE001 - job chua len
            pass
        time.sleep(2)
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    p = ctx.new_page()
    p.goto("http://localhost:4040/storage/")
    settle(p, 1)
    save(p, "hs_05_storage.png", "Spark UI (:4040) của 05 Phân tích hành vi khi đang chạy (100%, 2 worker, gốc đo /perf/s100) — "
                                 "tab Storage: các bảng đang cache")
    ctx.close()


def write_manifest():
    old = {}
    if os.path.exists(MANIFEST):
        old = {s["file"]: s for s in json.load(open(MANIFEST, encoding="utf-8")).get("files", [])}
    for s in shots:
        old[s["file"]] = s
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": datetime.now().isoformat(timespec="seconds"), "tool": "Playwright Chromium headless",
                   "files": sorted(old.values(), key=lambda s: s["file"]), "problems": problems}, fh,
                  ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="dashboard,perfcard,history,hdfs,mongo")
    ap.add_argument("--pages", default="", help="chi chup cac trang nay (slug, cach nhau dau phay)")
    args = ap.parse_args()
    groups = [g.strip() for g in args.only.split(",") if g.strip()]
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for g in groups:
                try:
                    if g == "dashboard":
                        dashboard(browser, [s for s in args.pages.split(",") if s] or
                                  [s for s, _, _ in PAGES if s != "thoi-gian-thuc"])
                    elif g == "realtime":
                        realtime(browser)
                    elif g == "stopped":
                        realtime(browser, stopped=True)
                    else:
                        globals()[g](browser)
                except Exception as e:  # noqa: BLE001 - nhom loi thi ghi lai, chup tiep nhom sau
                    problems.append(f"{g}: {type(e).__name__}: {str(e)[:200]}")
                    print(f"[shot] LOI nhom {g}: {e}", flush=True)
            browser.close()
    finally:
        write_manifest()
    print(f"[shot] {len(shots)} anh, {len(problems)} van de: {problems}", flush=True)


if __name__ == "__main__":
    main()
