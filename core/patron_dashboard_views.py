from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from app_settings.access import has_access
from attendance.models import AttendanceRecord
from .models import Order, OrderEvent, ProductionStageControlExclusion


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

    # 3 gündür hareket yok: mevcut Üretim Aşama Kontrolü ile aynı event/exclusion kuralı.
    cutoff = timezone.now() - timedelta(days=3)
    hidden_ids = set(ProductionStageControlExclusion.objects.filter(
        control_type__in=["unshipped_7d", "unshipped_3d_temp"]
    ).values_list("order_id", flat=True))
    latest_stage = {}
    for event in OrderEvent.objects.filter(
        order__in=open_orders, event_type="stage"
    ).only("order_id", "timestamp").order_by("order_id", "timestamp", "id"):
        latest_stage[event.order_id] = event.timestamp
    inactive_ids = [oid for oid, ts in latest_stage.items() if ts <= cutoff and oid not in hidden_ids]
    inactive_qs = open_orders.filter(id__in=inactive_ids)

    # Personel: patron/müdür hesaplarını puantaj toplamından çıkar.
    staff = request.user.__class__.objects.filter(is_active=True).exclude(
        Q(is_superuser=True) | Q(groups__name__in=["patron", "mudur"])
    ).distinct()
    today_records = AttendanceRecord.objects.filter(work_date=today, user__in=staff)
    arrived_ids = set(today_records.filter(check_in__isnull=False).values_list("user_id", flat=True))
    excused_ids = set(today_records.filter(status__in=["leave", "annual_leave", "sick"]).values_list("user_id", flat=True))
    late_today = today_records.filter(late_minutes__gt=0).count()
    absent_today = staff.exclude(id__in=arrived_ids | excused_ids).count()

    y_records = AttendanceRecord.objects.filter(work_date=yesterday, user__in=staff)
    early_yesterday = y_records.filter(early_leave_minutes__gt=0).count()
    overtime_yesterday = y_records.filter(overtime_minutes__gt=0).count()
    forgotten = y_records.filter(checkout_forgotten=True, checkout_forgotten_resolved_at__isnull=True).count()

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
        "staff_total": staff.count(), "arrived_count": len(arrived_ids),
        "absent_count": absent_today, "late_count": late_today,
        "early_yesterday": early_yesterday, "overtime_yesterday": overtime_yesterday,
        "forgotten_count": forgotten, "attention_count": attention_count,
        "finance": finance,
    }
    return render(request, "patron/dashboard.html", context)
