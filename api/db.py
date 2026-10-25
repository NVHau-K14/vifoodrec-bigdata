"""Ket noi MongoDB dung chung va do thoi gian truy van (header Server-Timing).

MONGO_URI, MONGO_DB lay tu bien moi truong (.env; compose dat MONGO_DB = ${API_DB:-vifood}).
"""
import contextvars
import os
import threading

from pymongo import MongoClient, monitoring

# Tong thoi gian lenh MongoDB (micro giay) cua request hien tai; middleware dat 1 list [0] cho moi request
db_micros = contextvars.ContextVar("db_micros", default=None)


class _DbTimer(monitoring.CommandListener):
    """pymongo dong bo goi listener tren chinh luong chay truy van -> cong vao request dang xu ly."""

    def started(self, event):
        pass

    def succeeded(self, event):
        acc = db_micros.get()
        if acc is not None:
            acc[0] += event.duration_micros

    def failed(self, event):
        self.succeeded(event)


_client = None
_lock = threading.Lock()


def db_name():
    return os.getenv("MONGO_DB", "vifood")


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = MongoClient(os.environ["MONGO_URI"], maxPoolSize=20, serverSelectionTimeoutMS=2000,
                                      appname="vifood-api", event_listeners=[_DbTimer()])
    return _client


def get_db():
    return get_client()[db_name()]
