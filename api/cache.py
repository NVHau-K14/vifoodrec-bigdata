"""Cache TTL trong RAM cho collection nho (D15): overview, reports, analysis_*, metrics, the mon gon.

Du lieu chi doi khi chay lai buoc 07, nen TTL 10 phut la du; clear() de test hoac nap lai ngay.
"""
import functools
import threading
import time

TTL_S = 600
_store = {}
_lock = threading.Lock()


def cached(fn):
    """Cache theo (ten ham, tham so). Ham tra ve du lieu dung chung: noi goi KHONG duoc sua ket qua."""
    @functools.wraps(fn)
    def wrapper(*args):
        key = (fn.__name__, args)
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < TTL_S:
            return hit[1]
        val = fn(*args)
        with _lock:
            _store[key] = (time.monotonic(), val)
        return val
    return wrapper


def clear():
    with _lock:
        _store.clear()
