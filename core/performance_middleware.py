import time
from collections import defaultdict, deque
from threading import Lock

from django.db import connection

_lock = Lock()
_samples = defaultdict(lambda: deque(maxlen=200))

SKIP_PREFIXES = ("/static/", "/media/", "/health/", "/sistem-sagligi/data/")


def record_sample(path, method, status, elapsed_ms, queries, db_ms=0):
    with _lock:
        _samples[path].append({
            "method": method,
            "status": status,
            "ms": round(elapsed_ms, 1),
            "queries": queries,
            "db_ms": round(db_ms, 1),
            "at": time.time(),
        })


def performance_snapshot():
    rows = []
    with _lock:
        data = {path: list(values) for path, values in _samples.items()}
    for path, values in data.items():
        if not values:
            continue
        times = sorted(v["ms"] for v in values)
        q = [v["queries"] for v in values if v["queries"] is not None]
        db = [v.get("db_ms", 0) for v in values]
        idx95 = min(len(times) - 1, max(0, int(len(times) * .95) - 1))
        avg = sum(times) / len(times)
        rows.append({
            "path": path,
            "count": len(values),
            "avg_ms": round(avg, 1),
            "p95_ms": round(times[idx95], 1),
            "max_ms": round(max(times), 1),
            "avg_queries": round(sum(q) / len(q), 1) if q else None,
            "avg_db_ms": round(sum(db) / len(db), 1) if db else 0,
            "errors": sum(1 for v in values if v["status"] >= 500),
            "level": "danger" if avg >= 2000 else "warn" if avg >= 1000 else "ok",
        })
    return sorted(rows, key=lambda x: x["avg_ms"], reverse=True)


class _DBTimer:
    def __init__(self):
        self.count = 0
        self.ms = 0.0

    def __call__(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.ms += (time.perf_counter() - started) * 1000


class PerformanceMonitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        timer = _DBTimer()
        with connection.execute_wrapper(timer):
            response = self.get_response(request)
        elapsed = (time.perf_counter() - start) * 1000
        path = request.path

        # Browser tarafı da bu değerleri okuyup yavaşlığın kaynağını gösterebilir.
        response["Server-Timing"] = (
            f'app;dur={elapsed:.1f}, db;dur={timer.ms:.1f};desc="DB", '
            f'dbq;dur={timer.count:.0f};desc="DB queries"'
        )

        if getattr(request.user, "is_authenticated", False) and not path.startswith(SKIP_PREFIXES):
            record_sample(path, request.method, response.status_code, elapsed, timer.count, timer.ms)
        return response
