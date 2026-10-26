"""pytest cho API buoc 08 (D15). Goi app ngay trong tien trinh (TestClient), doc MongoDB that.

Chay trong container api (tu /home/jovyan/work):
  python -m pytest -q api/tests                       (mac dinh database vifood, ban day du dung cho demo)
  python -m pytest -q api/tests --db vifood_local     (ban 10% do 07 --local ghi; da xoa 26/10, chay 05/07 --local de tao lai)
Kiem tra la bat bien, dung voi ca hai database.
"""
import hashlib
import os

import pytest


def pytest_addoption(parser):
    parser.addoption("--db", default="vifood", help="database MongoDB de kiem tra")


def pytest_configure(config):
    # Dat truoc khi import api: db.py doc MONGO_DB moi lan goi get_db()
    os.environ["MONGO_DB"] = config.getoption("--db")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db():
    from api.db import get_db
    return get_db()


@pytest.fixture(scope="session")
def full_db(request):
    """So sanh chinh xac giua cac collection chi dung voi vifood: o vifood_local, analysis_* cu hon overview
    va reports la file cua lan chay tren cum, con metrics la ket qua local."""
    if request.config.getoption("--db") != "vifood":
        pytest.skip("chỉ kiểm tra với --db vifood")


def by_hash(ids, n):
    """Chon n phan tu co dinh theo md5 (chay lai ra cung mau)."""
    return sorted(ids, key=lambda i: hashlib.md5(str(i).encode()).hexdigest())[:n]


@pytest.fixture(scope="session")
def sample_users(db):
    """50 user theo hash, du ca 3 nhom am / it / lanh."""
    out = []
    for g, n in (("ấm", 40), ("ít", 5), ("lạnh", 5)):
        ids = [u["_id"] for u in db.users.find({"group": g}, {"_id": 1})]
        out += by_hash(ids, n)
    return out


def find_key(obj, key, substring=False):
    """True neu khoa key (hoac khoa chua key khi substring) xuat hien o bat ky tang nao cua obj."""
    if isinstance(obj, dict):
        hit = any(key in k for k in obj) if substring else key in obj
        return hit or any(find_key(v, key, substring) for v in obj.values())
    if isinstance(obj, list):
        return any(find_key(v, key, substring) for v in obj)
    return False
