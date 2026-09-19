import time
from collections import defaultdict, deque
from threading import Lock

from django.db import connection

_lock = Lock()
_samples = defaultdict(lambda: deque(maxlen=200))

SKIP_PREFIXES = ("/static/", "/media/", "/health/", "/sistem-sagligi/data/")
# Monitoring marker: keep middleware changes in the current deploy.


def record_sample(path, method, status, elapsed_ms, queries):
    with _lock:
        _samples[path].append({
            "method": method,
            "status": status,
            "ms": round(elapsed_ms, 1),
            "queries": queries,
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
        idx95 = min(len(times) - 1, max(0, int(len(times) * .95) - 1))
        avg = sum(times) / len(times)
        rows.append({
            "path": path,
            "count": len(values),
            "avg_ms": round(avg, 1),
            "p95_ms": round(times[idx95], 1),
            "max_ms": round(max(times), 1),
            "avg_queries": round(sum(q) / len(q), 1) if q else None,
            "errors": sum(1 for v in values if v["status"] >= 500),
            "level": "danger" if avg >= 2000 else "warn" if avg >= 1000 else "ok",
        })
    return sorted(rows, key=lambda x: x["avg_ms"], reverse=True)


class PerformanceMonitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        before = len(connection.queries)
        response = self.get_response(request)
        elapsed = (time.perf_counter() - start) * 1000
        path = request.path
        if request.user.is_authenticated and not path.startswith(SKIP_PREFIXES):
            after = len(connection.queries)
            queries = after - before if connection.queries else None
            record_sample(path, request.method, response.status_code, elapsed, queries)
        return response
