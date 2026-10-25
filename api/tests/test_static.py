"""web/ tinh duoc phuc vu cung origin; /api/... khong ton tai tra 404 JSON."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"
PAGES = ["index.html", "hanh-vi.html", "mon-an.html", "phan-khuc.html", "goi-y.html", "danh-gia.html",
         "thoi-gian-thuc.html"]


def test_pages_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "<title>Tổng quan" in r.text
    for p in PAGES:
        r = client.get(f"/{p}")
        assert r.status_code == 200, p
        assert r.headers["cache-control"] == "no-cache"


def test_vendor_and_fonts(client):
    r = client.get("/vendor/echarts.min.js")
    assert r.status_code == 200 and len(r.content) > 900_000
    assert "max-age" in r.headers["cache-control"]
    fonts = sorted(p.name for p in (WEB / "fonts").glob("*.woff2"))
    assert len(fonts) == 12
    for f in fonts:
        assert client.get(f"/fonts/{f}").status_code == 200


def test_gzip(client):
    r = client.get("/vendor/echarts.min.js", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_api_404_is_json(client):
    r = client.get("/api/khong-co")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert r.json()["detail"].startswith("Không có endpoint")


def test_server_timing_header(client):
    r = client.get("/api/overview")
    assert r.headers["server-timing"].startswith("app;dur=")
