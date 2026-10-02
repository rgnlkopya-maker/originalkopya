from datetime import timedelta
from decimal import Decimal
import json
import urllib.parse
import urllib.request

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from app_settings.access import has_access
from attendance.models import AttendanceRecord
from product_cards.models import PriceListSettings
from product_cards.price_list_views import _ensure_price_rates
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


def _today_staff_summary(user):
    today = timezone.localdate()
    staff = user.__class__.objects.filter(is_active=True).exclude(
        Q(is_superuser=True) | Q(groups__name__in=["patron", "mudur"])
    ).distinct()

    records = AttendanceRecord.objects.filter(work_date=today, user__in=staff)
    worked = records.filter(status="worked")
    excused_user_ids = set(
        records.exclude(status="worked").values_list("user_id", flat=True)
    )

    arrived_user_ids = set(
        worked.filter(check_in__isnull=False).values_list("user_id", flat=True)
    )
    arrived = len(arrived_user_ids)
    late = worked.filter(check_in__isnull=False, late_minutes__gt=0).count()
    inside = worked.filter(check_in__isnull=False, check_out__isnull=True).count()
    checked_out = worked.filter(check_out__isnull=False).count()

    if today.weekday() < 5:
        absent = staff.exclude(id__in=arrived_user_ids | excused_user_ids).count()
    else:
        absent = 0

    incomplete = AttendanceRecord.objects.filter(
        user__in=staff,
        checkout_forgotten=True,
        checkout_forgotten_resolved_at__isnull=True,
    ).count()

    return {
        "arrived": arrived,
        "late": late,
        "absent": absent,
        "inside": inside,
        "checked_out": checked_out,
        "incomplete": incomplete,
        "checked_at": timezone.localtime().strftime("%H:%M"),
    }


@login_required
def patron_staff_summary(request):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()):
        return JsonResponse({"ok": False}, status=403)
    return JsonResponse({"ok": True, **_today_staff_summary(request.user)})


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
    due_3_qs = open_orders.filter(
        teslim_tarihi__gt=today,
        teslim_tarihi__lte=today + timedelta(days=3),
    )
    due_7_qs = open_orders.filter(
        teslim_tarihi__gt=today + timedelta(days=3),
        teslim_tarihi__lte=today + timedelta(days=7),
    )

    # Dünün üretim özeti: aynı sipariş aynı işlem için birden çok event üretse bile
    # yalnızca bir kez sayılır; sayı sipariş adedi toplamıdır.
    def yesterday_stage_qty(stage, value):
        order_ids = (
            OrderEvent.objects.filter(
                timestamp__date=yesterday,
                event_type="stage",
                stage=stage,
                value=value,
            )
            .values_list("order_id", flat=True)
            .distinct()
        )
        return qty(
            Order.objects.filter(id__in=order_ids)
            .exclude(siparis_tipi="MALZEME")
        )

    production = [
        ("Kesildi", yesterday_stage_qty("kesim_durum", "bitti"), "bi-scissors", "kesim_durum", "bitti"),
        ("Dikildi", yesterday_stage_qty("dikim_durum", "bitti"), "bi-tools", "dikim_durum", "bitti"),
        ("Süslendi", yesterday_stage_qty("susleme_durum", "bitti"), "bi-stars", "susleme_durum", "bitti"),
        ("Hazırlandı", yesterday_stage_qty("hazir_durum", "bitti"), "bi-check2-circle", "hazir_durum", "bitti"),
        ("Konsinyeye Verildi", yesterday_stage_qty("konsinye_durum", "verildi"), "bi-box-arrow-up-right", "konsinye_durum", "verildi"),
        ("Sevk Edildi", yesterday_stage_qty("sevkiyat_durum", "gonderildi"), "bi-truck", "sevkiyat_durum", "gonderildi"),
    ]

    # Sevkiyat: mevcut alan + sevkiyat event fallback.
    shipped_ids = set(active.filter(sevkiyat_tarihi=yesterday).values_list("id", flat=True))
    shipped_ids.update(OrderEvent.objects.filter(
        timestamp__date=yesterday, event_type="stage", stage="sevkiyat_durum", value="gonderildi"
    ).values_list("order_id", flat=True))
    yesterday_shipped = active.filter(id__in=shipped_ids)
    yesterday_shipped_qty = qty(yesterday_shipped)

    # Dün sisteme yeni girilen siparişler (sevkiyattan bağımsız).
    yesterday_new_orders = active.filter(siparis_tarihi=yesterday)
    yesterday_new_count = yesterday_new_orders.count()
    yesterday_new_qty = qty(yesterday_new_orders)

    # Üretim Aşama Kontrolü ile aynı ortak hareketsiz sipariş kaynağı.
    inactive_rows = get_unshipped_inactive_orders(request.user)
    inactive_ids = [row["order"].id for row in inactive_rows]
    inactive_qs = open_orders.filter(id__in=inactive_ids)

    # Bugünün personel özeti canlı kartlarda kullanılır.
    staff_summary = _today_staff_summary(request.user)
    forgotten = staff_summary["incomplete"]

    weather = _izmir_weather()
    rate_settings = PriceListSettings.get_solo()
    _ensure_price_rates(rate_settings)
    rate_info = {
        "usd": rate_settings.usd_try,
        "eur": rate_settings.eur_try,
        "gbp": rate_settings.gbp_try,
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

    attention_count = overdue_qs.count() + due_today_qs.count() + due_3_qs.count() + due_7_qs.count()
    context = {
        "today": today, "yesterday": yesterday,
        "ready_count": ready_qs.count(), "ready_qty": qty(ready_qs),
        "overdue_count": overdue_qs.count(), "overdue_qty": qty(overdue_qs),
        "due_today_count": due_today_qs.count(), "due_today_qty": qty(due_today_qs),
        "due_3_count": due_3_qs.count(), "due_3_qty": qty(due_3_qs),
        "due_7_count": due_7_qs.count(), "due_7_qty": qty(due_7_qs),
        "production": production,
        "shipped_count": yesterday_shipped.count(), "shipped_qty": yesterday_shipped_qty,
        "yesterday_new_count": yesterday_new_count, "yesterday_new_qty": yesterday_new_qty,
        "inactive_count": inactive_qs.count(), "inactive_qty": qty(inactive_qs),
        "forgotten_count": forgotten, "attention_count": attention_count,
        "staff_summary": staff_summary,
        "finance": finance, "weather": weather, "rate_info": rate_info,
    }
    return render(request, "patron/dashboard.html", context)
