"""
main.py - FastAPI cho dashboard ViFoodRec (buoc 08, D15).

Dau vao : MongoDB database MONGO_DB (vifood khi demo, vifood_local khi phat trien), do buoc 07 ghi.
Dau ra  : /api/... (JSON, tai lieu o /docs) va web/ tinh tren cung origin (khong can CORS).

Chay (service api trong docker/docker-compose.yml):
  docker compose up -d --build api            -> http://localhost:8000
  $env:API_DB="vifood_local"; docker compose up -d api      (PowerShell, doi sang database phat trien)
Sua api/*.py xong: docker restart api. Sua web/ chi can tai lai trang.
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import ConnectionFailure

from .db import db_micros
from .dishes_common import cards
from .routers import behavior, dishes, evaluation, overview, realtime, recs, segments

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app):
    # Nap san cache (the mon, user mau); MongoDB chua san sang thi van khoi dong, request se tra 503
    try:
        t = time.perf_counter()
        cards()
        recs.demo_users()
        log.info("[08] nap cache %.0f ms", (time.perf_counter() - t) * 1000)
    except ConnectionFailure as e:
        log.warning("[08] chua ket noi duoc MongoDB: %s", e)
    yield


app = FastAPI(title="ViFoodRec API", version="0.1", lifespan=lifespan,
              description="API của dashboard ViFoodRec. Dữ liệu hành vi là **mô phỏng**; danh mục món là món thật.")


class ServerTiming:
    """Middleware ASGI: them header Server-Timing (app = tong thoi gian, db = thoi gian lenh MongoDB)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        acc = [0]
        token = db_micros.set(acc)
        t0 = time.perf_counter()

        async def send_wrapper(msg):
            if msg["type"] == "http.response.start":
                dur = (time.perf_counter() - t0) * 1000
                msg.setdefault("headers", []).append(
                    (b"server-timing", f"app;dur={dur:.2f}, db;dur={acc[0] / 1000:.2f}".encode()))
            await send(msg)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            db_micros.reset(token)


app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(ServerTiming)


@app.exception_handler(ConnectionFailure)
async def mongo_down(request: Request, exc: ConnectionFailure):
    return JSONResponse({"detail": "Không kết nối được MongoDB"}, status_code=503)


api = APIRouter(prefix="/api")
for r in (overview.router, behavior.router, dishes.router, dishes.ing_router, segments.router, recs.router,
          evaluation.router, realtime.router):
    api.include_router(r)


@api.api_route("/{path:path}", methods=["GET", "POST"], include_in_schema=False)
def api_not_found(path: str):
    # /api/... khong ton tai -> 404 JSON, khong roi xuong web/ tinh
    raise HTTPException(404, f"Không có endpoint /api/{path}")


app.include_router(api)


class WebFiles(StaticFiles):
    """web/ tinh: vendor/ va fonts/ cache 7 ngay; HTML, CSS, JS no-cache de sua xong chi can tai lai trang."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        long_cache = path.startswith(("vendor/", "fonts/", "vendor\\", "fonts\\"))
        resp.headers["Cache-Control"] = "public, max-age=604800" if long_cache else "no-cache"
        return resp


app.mount("/", WebFiles(directory=WEB_DIR, html=True), name="web")
