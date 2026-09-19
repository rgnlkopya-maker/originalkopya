import time

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .models import Order, OrderEvent, Musteri, AuditLog
from .performance_middleware import performance_snapshot


def _manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


@login_required
def system_health(request):
    if not _manager(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    checks = []
    started = time.perf_counter()
    db_ok = True
    db_error = ""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        db_error = str(exc)[:160]
    db_ms = round((time.perf_counter() - started) * 1000, 1)
    checks.append({"name": "Veritabanı bağlantısı", "ok": db_ok, "detail": f"{db_ms} ms" if db_ok else db_error})

    counts = {
        "Sipariş": Order.objects.count(),
        "Üretim hareketi": OrderEvent.objects.count(),
        "Müşteri": Musteri.objects.count(),
        "İşlem kaydı": AuditLog.objects.count(),
    }
    checks.append({"name": "Veritabanı yanıtı", "ok": db_ms < 500, "detail": "Normal" if db_ms < 500 else "Yavaş"})
    checks.append({"name": "500 hata takibi", "ok": all(r["errors"] == 0 for r in performance_snapshot()), "detail": "Ölçülen isteklerde kontrol edildi"})

    return render(request, "system_health.html", {
        "checks": checks,
        "rows": performance_snapshot(),
        "counts": counts,
        "db_ms": db_ms,
    })
