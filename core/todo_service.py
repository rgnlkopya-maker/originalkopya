from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .push_views import send_push_to_user
from .todo_models import TodoItem


def process_due_todos(now=None):
    now = now or timezone.now()
    items = TodoItem.objects.filter(
        completed_at__isnull=True,
        alarm_enabled=True,
        due_at__isnull=False,
        due_at__lte=now,
    ).select_related("user")
    notified = delivered = 0
    for item in items:
        if item.snoozed_until and item.snoozed_until > now:
            continue
        interval = max(5, int(item.alarm_interval_minutes or 15))
        with transaction.atomic():
            locked = TodoItem.objects.select_for_update().get(pk=item.pk)
            if locked.completed_at or not locked.alarm_enabled:
                continue
            if locked.snoozed_until and locked.snoozed_until > now:
                continue
            if locked.last_notified_at and now - locked.last_notified_at < timedelta(minutes=interval):
                continue
            locked.last_notified_at = now
            locked.save(update_fields=["last_notified_at"])
        notified += 1
        due_label = timezone.localtime(item.due_at).strftime("%d.%m.%Y %H:%M")
        note = " ".join((item.note or "").split())
        details = f"Planlanan: {due_label}"
        if note:
            details += f"  |  Not: {note[:140]}"
        details += "  |  Açmak için dokunun."
        delivered += send_push_to_user(
            user=item.user,
            title=f"Yapılacak İş • {item.title[:90]}",
            body=details,
            url="/yapilacaklar/",
            tag=f"moli-todo-{item.id}",
        )
    try:
        process_daily_management_alerts(now=now)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Daily management alerts failed")
    return {"notified": notified, "delivered": delivered}


def process_daily_management_alerts(now=None):
    """One daily 13:30 management digest per alert category (Istanbul local time).

    Read-only operational checks: no order, instrument or stage records are
    changed. Repeated minute ticks do not produce duplicate notifications.
    """
    from datetime import timedelta
    from django.core.cache import cache
    from django.db.models import Max, Q
    from .models import Order, OrderEvent, Notification, ProductionStageControlExclusion
    from .instrument_models import NegotiableInstrument
    from .manager_notification_signals import notify_management, management_users

    now = now or timezone.now()
    local = timezone.localtime(now)
    if local.hour != 13 or local.minute < 30:
        return {"skipped": "outside_13_30_window"}

    today = local.date()
    tomorrow = today + timedelta(days=1)
    results = {}

    def publish(key, title, summary, url):
        # The database record prevents repeats even after application restart.
        stamp = f"[{key}:{today.isoformat()}]"
        if Notification.objects.filter(title=title, message__startswith=stamp).exists():
            return "already_sent"
        lock = f"scheduled-management-alert:{key}:{today.isoformat()}"
        if not cache.add(lock, "1", timeout=3600):
            return "already_processing"
        try:
            if not management_users().exists():
                return "no_managers"
            notify_management(title, f"{stamp} {summary}", url)
            return "sent"
        except Exception:
            cache.delete(lock)
            raise

    # Due to ship tomorrow, but not yet shipped. The delivery date in the
    # order is the source of truth; group into one digest to avoid alert floods.
    due_orders = list(
        Order.objects.filter(is_active=True, teslim_tarihi=tomorrow)
        .exclude(siparis_tipi="MALZEME")
        .exclude(sevkiyat_durum="gonderildi")
        .select_related("musteri").order_by("siparis_numarasi")
    )
    if due_orders:
        examples = [
            f"{o.siparis_numarasi} {o.urun_kodu or ''} ({o.musteri.ad if o.musteri else 'Stok'})"
            for o in due_orders[:8]
        ]
        summary = f"Yarın ({tomorrow:%d.%m.%Y}) teslim tarihli, henüz sevk edilmemiş {len(due_orders)} sipariş var: " + "; ".join(examples)
        if len(due_orders) > 8:
            summary += f"; ve {len(due_orders)-8} sipariş daha."
        results["tomorrow_shipping"] = publish("tomorrow-shipping", "Yarın Teslim Edilecek Siparişler", summary, "/")

    # Match the existing production-stage-control 3-day inactivity rule.
    # Limit to orders with actual stage history and without a completed shipment.
    cutoff = now - timedelta(days=3)
    exclusions = ProductionStageControlExclusion.objects.filter(
        control_type__in=["unshipped_7d", "unshipped_3d_temp"],
    ).values_list("order_id", flat=True)
    stalled = list(
        Order.objects.filter(is_active=True)
        .exclude(siparis_tipi="MALZEME")
        .exclude(sevkiyat_durum="gonderildi")
        .exclude(id__in=exclusions)
        .annotate(last_stage_at=Max("events__timestamp", filter=Q(events__event_type="stage")))
        .filter(last_stage_at__isnull=False, last_stage_at__lte=cutoff)
        .select_related("musteri")
        .order_by("last_stage_at")[:100]
    )
    if stalled:
        examples = [f"{o.siparis_numarasi} ({(now-o.last_stage_at).days} gün)" for o in stalled[:8]]
        summary = f"En az 3 gündür üretim hareketi olmayan {len(stalled)} sipariş bulundu"
        if len(stalled) == 100:
            summary += " (ilk 100 kayıt)"
        summary += ": " + "; ".join(examples)
        results["stalled_production"] = publish("stalled-production", "Üretim Aşaması Takıldı", summary, "/uretim-asama-kontrolu/")

    # Explicitly payment-pending outgoing documents only (not receivables).
    due_date = today + timedelta(days=15)
    payable = list(
        NegotiableInstrument.objects.filter(
            direction="OUT", status="ISSUED", due_date=due_date,
            kind__in=["CK_OWN", "NT_OWN"],
        ).order_by("id")
    )
    if payable:
        labels = []
        for item in payable[:8]:
            unit = {"TRY": "TL", "USD": "USD", "EUR": "EUR", "GBP": "GBP"}.get(item.currency, item.currency)
            labels.append(f"#{item.pk} {item.get_kind_display()} {item.amount} {unit}")
        summary = f"Vadesine 15 gün kalan {len(payable)} ödeme bekleyen çek/senet var (vade {due_date:%d.%m.%Y}): " + "; ".join(labels)
        if len(payable) > 8:
            summary += f"; ve {len(payable)-8} evrak daha."
        results["payable_instruments"] = publish("payable-instruments", "Çek/Senet Vadesine 15 Gün Kaldı", summary, "/muhasebe/cek-senet/")

    return results
