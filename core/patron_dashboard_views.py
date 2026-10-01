from datetime import timedelta
from decimal import Decimal
import json
import urllib.parse
import urllib.request

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from app_settings.access import has_access
from attendance.models import AttendanceRecord
from product_cards.models import PriceListSettings
from .models import Order, OrderEvent
from .production_stage_control_views import get_unshipped_inactive_orders


def _izmir_weather():
    """İzmir için günün hava özetini kısa süreli cache ile getir."""
    key = f"patron:izmir-weather:{timezone.localdate().isoformat()}"
    cached = cache.get(key)
    if cached:
        return cached
    params = urllib.parse.urlencode({
        "latitude": "38.4237",
        "longitude": "27.1428",
        "current": "temperature_2m,weather_code",
        "daily": "precipitation_probability_max",
        "timezone": "Europe/Istanbul",
        "forecast_days": "1",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MoliApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        code = int((data.get("current") or {}).get("weather_code", 0))
        temp = (data.get("current") or {}).get("temperature_2m")
        rain = ((data.get("daily") or {}).get("precipitation_probability_max") or [None])[0]
        if code == 0:
            label, icon = "Güneşli", "bi-sun"
        elif code in {1, 2}:
            label, icon = "Parçalı bulutlu", "bi-cloud-sun"
        elif code == 3:
            label, icon = "Bulutlu", "bi-clouds"
        elif code in {45, 48}:
            label, icon = "Sisli", "bi-cloud-fog2"
        elif code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
            label, icon = "Yağışlı", "bi-cloud-rain"
        elif code in {71, 73, 75, 77, 85, 86}:
            label, icon = "Karlı", "bi-snow"
        elif code in {95, 96, 99}:
            label, icon = "Fırtınalı", "bi-cloud-lightning-rain"
        else:
            label, icon = "Hava durumu", "bi-cloud"
        result = {
            "label": label,
            "icon": icon,
            "temperature": round(float(temp)) if temp is not None else None,
            "rain": int(rain) if rain is not None else None,
            "checked_at": timezone.localtime().strftime("%H:%M"),
        }
        cache.set(key, result, 60 * 60 * 6)
        return result
    except Exception:
        return None


@login_required
def patron_dashboard(request):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    now = timezone.localtime()
    today = now.date()
    yesterday = today - timedelta(days=1)
    while yesterday.weekday() >= 5:
        yesterday -= timedelta(days=1)

    active = Order.objects.filter(is_active=True).exclude(siparis_tipi="MALZEME")
    open_orders = active.exclude(sevkiyat_durum="gonderildi")

    def qty(qs):
        return qs.aggregate(v=Coalesce(Sum("adet"), 0))["v"] or 0

    # Sabah nabzı
    ready_qs = open_orders.filter(hazir_durum="bitti")
    overdue_qs = open_orders.filter(teslim_tarihi__lt=today)
    due_today_qs = open_orders.filter(teslim_tarihi=today)
    due_tomorrow_qs = open_orders.filter(teslim_tarihi=today + timedelta(days=1))
    due_3_qs = open_orders.filter(teslim_tarihi__gt=today + timedelta(days=1), teslim_tarihi__lte=today + timedelta(days=3))

    # Üretim: o aşamada başlamış ve henüz bitmemiş işler.
    production = [
        ("Kesim", qty(open_orders.filter(kesim_durum="basladi")), "bi-scissors"),
        ("Dikim", qty(open_orders.filter(dikim_durum="basladi")), "bi-thread"),
        ("Süsleme", qty(open_orders.filter(susleme_durum="basladi")), "bi-stars"),
        ("Nakış", qty(open_orders.filter(nakis_durumu="verildi")), "bi-flower1"),
        ("Hazır", qty(ready_qs), "bi-check2-circle"),
    ]

    yesterday_events = OrderEvent.objects.filter(
        timestamp__date=yesterday, event_type="stage", value="bitti"
    )
    completed = []
    for stage, label in [
        ("kesim_durum", "Kesim"),
        ("dikim_durum", "Dikim"),
        ("susleme_durum", "Süsleme"),
        ("hazir_durum", "Hazır"),
    ]:
        completed.append((label, yesterday_events.filter(stage=stage).aggregate(v=Coalesce(Sum("adet"), 0))["v"] or yesterday_events.filter(stage=stage).count()))

    # Sevkiyat: mevcut alan + sevkiyat event fallback.
    shipped_ids = set(active.filter(sevkiyat_tarihi=yesterday).values_list("id", flat=True))
    shipped_ids.update(OrderEvent.objects.filter(
        timestamp__date=yesterday, event_type="stage", stage="sevkiyat_durum", value="gonderildi"
    ).values_list("order_id", flat=True))
    yesterday_shipped = active.filter(id__in=shipped_ids)
    yesterday_shipped_qty = qty(yesterday_shipped)

    # Üretim Aşama Kontrolü ile aynı ortak hareketsiz sipariş kaynağı.
    inactive_rows = get_unshipped_inactive_orders(request.user)
    inactive_ids = [row["order"].id for row in inactive_rows]
    inactive_qs = open_orders.filter(id__in=inactive_ids)

    # Personel geldi/gelmedi özeti Patron Ekranı'ndan kaldırıldı.
    # Sadece aksiyon gerektiren unutulan çıkış sayısı uyarılar için korunuyor.
    staff = request.user.__class__.objects.filter(is_active=True).exclude(
        Q(is_superuser=True) | Q(groups__name__in=["patron", "mudur"])
    ).distinct()
    y_records = AttendanceRecord.objects.filter(work_date=yesterday, user__in=staff)
    forgotten = y_records.filter(checkout_forgotten=True, checkout_forgotten_resolved_at__isnull=True).count()

    weather = _izmir_weather()
    rate_settings = PriceListSettings.get_solo()
    rate_info = {
        "usd": rate_settings.usd_try,
        "eur": rate_settings.eur_try,
        "source": rate_settings.rate_source,
        "checked_at": timezone.localtime(rate_settings.rate_checked_at).strftime("%H:%M") if rate_settings.rate_checked_at else "",
    }

    # Finans: sevk edilen siparişlerin mevcut snapshot alanlarından, para birimi bazında.
    finance = []
    for currency in ("TRY", "USD", "EUR"):
        rows = yesterday_shipped.filter(para_birimi=currency)
        revenue = sum((o.satis_fiyati or Decimal("0")) for o in rows)
        cost = sum(((o.maliyet_override if o.maliyet_override is not None else o.maliyet_uygulanan) or Decimal("0")) + (o.ekstra_maliyet or Decimal("0")) for o in rows)
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue else Decimal("0")
        if rows.exists():
            finance.append({"currency": currency, "revenue": revenue, "cost": cost, "profit": profit, "margin": margin})

    attention_count = overdue_qs.count() + inactive_qs.count() + forgotten
    context = {
        "today": today, "yesterday": yesterday,
        "ready_count": ready_qs.count(), "ready_qty": qty(ready_qs),
        "overdue_count": overdue_qs.count(), "overdue_qty": qty(overdue_qs),
        "due_today_count": due_today_qs.count(), "due_today_qty": qty(due_today_qs),
        "due_tomorrow_count": due_tomorrow_qs.count(), "due_tomorrow_qty": qty(due_tomorrow_qs),
        "due_3_count": due_3_qs.count(), "due_3_qty": qty(due_3_qs),
        "production": production, "completed": completed,
        "shipped_count": yesterday_shipped.count(), "shipped_qty": yesterday_shipped_qty,
        "inactive_count": inactive_qs.count(), "inactive_qty": qty(inactive_qs),
        "forgotten_count": forgotten, "attention_count": attention_count,
        "finance": finance, "weather": weather, "rate_info": rate_info,
    }
    return render(request, "patron/dashboard.html", context)
