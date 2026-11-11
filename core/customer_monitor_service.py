"""Daily customer-status and leaderboard alerts, using the customer comparison rules."""
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import CustomerMonitorState, Musteri

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "aktif": "AKTİF",
    "dikkat": "DİKKAT",
    "pasif": "UYKUN",
}
LEADER_TYPES = {
    "profit": ("En Kârlı Müşteri Değişti", "en kârlı", "kâr", "TL"),
    "quantity": ("En Fazla Adet Alan Müşteri Değişti", "en fazla adet alan", "sevk edilen adet", "adet"),
    "revenue": ("En Yüksek Ciroya Sahip Müşteri Değişti", "en yüksek ciro yapan", "ciro", "TL"),
    "profit_min": ("En Düşük Kârlı Müşteri Değişti", "en düşük kârı olan", "kâr", "TL"),
    "quantity_min": ("En Az Adet Alan Müşteri Değişti", "en az adet alan", "sevk edilen adet", "adet"),
    "revenue_min": ("En Düşük Ciroya Sahip Müşteri Değişti", "en düşük ciro yapan", "ciro", "TL"),
}


def _status(last_shipment, today):
    days = (today - last_shipment).days
    if days <= 90:
        return "aktif", days
    if days <= 180:
        return "dikkat", days
    return "pasif", days


def _money(value):
    # Turkish thousands separator, without hidden rounding in the comparison.
    return f"{value:,.0f}".replace(",", ".")


def _capture_once(key, today, payload, publish):
    """One persistent daily snapshot per category; do not notify on first run.

    Row locks and unique keys make the comparison idempotent across cron retries
    and concurrent workers. Notifications are saved in the same transaction;
    browser push is dispatched only after commit.
    """
    with transaction.atomic():
        state, created = CustomerMonitorState.objects.select_for_update().get_or_create(
            key=key, defaults={"payload":payload, "last_checked_on":today},
        )
        if created:
            return {"baseline": True, "sent": 0}
        if state.last_checked_on == today:
            return {"already_checked": True, "sent": 0}
        old_payload = state.payload if isinstance(state.payload, dict) else {}
        sent = publish(old_payload, payload)
        state.payload = payload
        state.last_checked_on = today
        state.save(update_fields=["payload", "last_checked_on", "updated_at"])
    return {"sent": sent}


def _notify_status(old, current):
    from .manager_notification_signals import notify_management

    sent = 0
    names = dict(Musteri.objects.filter(
        pk__in=[int(cid) for cid in current if cid.isdecimal()]
    ).values_list("id", "ad"))
    for cid, data in current.items():
        before = old.get(cid)
        if not isinstance(before, dict) or before.get("status") == data["status"]:
            continue
        previous = before.get("status")
        if previous not in STATUS_LABELS:
            continue
        name = names.get(int(cid), f"Müşteri #{cid}")
        old_label = STATUS_LABELS[previous]
        new_label = STATUS_LABELS[data["status"]]
        if data["status"] == "aktif":
            reason = "Yeni sevkiyatla yeniden aktif müşteriler arasına girdi."
        else:
            reason = f"Son sevkiyatının üzerinden {data['days']} gün geçti."
        message = (
            f"{name} müşterisinin durumu {old_label} → {new_label} olarak değişti. "
            f"{reason} Son sevkiyat: {data['last_shipment']}. "
            "Ayrıntılar için müşterinin performans sayfasını açın."
        )
        notify_management(
            "Müşteri Durumu Değişti",
            message,
            reverse("customer_comparison_report"),
        )
        sent += 1
    return sent


def _collect_statuses(rows, today):
    dates = {}
    for row in rows:
        customer_id = str(row["order"].musteri_id)
        shipped = row["ship_date"]
        if shipped and (customer_id not in dates or shipped > dates[customer_id]):
            dates[customer_id] = shipped
    result = {}
    for cid, shipped in dates.items():
        status, days = _status(shipped, today)
        result[cid] = {
            "status": status,
            "last_shipment": shipped.strftime("%d.%m.%Y"),
            "days": days,
        }
    return result


def _collect_leaders(rows):
    grouped = defaultdict(lambda: {
        "profit": Decimal("0"),
        "revenue": Decimal("0"),
        "quantity": 0,
    })
    for row in rows:
        order = row["order"]
        cid = order.musteri_id
        record = grouped[cid]
        record["quantity"] += int(order.adet or 1)
        result = row["result"]
        if result.get("is_final"):
            record["revenue"] += Decimal(result.get("satis_tl") or 0)
            record["profit"] += Decimal(result.get("kar_tl") or 0)

    if not grouped:
        return {metric: None for metric in LEADER_TYPES}
    customers = dict(Musteri.objects.filter(pk__in=grouped.keys()).values_list("id", "ad"))
    leaders = {}
    for metric in LEADER_TYPES:
        base_metric = metric.removesuffix("_min")
        # A stable customer ID tie-break keeps both top and bottom rankings
        # from switching solely because of queryset ordering.
        if metric.endswith("_min"):
            winner_id = min(grouped, key=lambda cid: (grouped[cid][base_metric], cid))
        else:
            winner_id = min(grouped, key=lambda cid: (-grouped[cid][base_metric], cid))
        leaders[metric] = {
            "id": winner_id,
            "name": customers.get(winner_id, f"Müşteri #{winner_id}"),
            "value": str(grouped[winner_id][base_metric]),
        }
    return leaders


def _notify_leaders(old, current):
    from .manager_notification_signals import notify_management

    sent = 0
    for metric, spec in LEADER_TYPES.items():
        previous = old.get(metric)
        leader = current.get(metric)
        if not leader or not isinstance(leader, dict):
            continue
        # A newly introduced ranking needs its first baseline, not a false
        # "leader changed" notification for existing users.
        if not isinstance(previous, dict) or not previous:
            continue
        old_id = str(previous.get("id")) if isinstance(previous, dict) and previous else None
        if old_id == str(leader["id"]):
            continue
        title, phrase, measure, unit = spec
        previous_name = previous.get("name", "Henüz lider yok") if isinstance(previous, dict) else "Henüz lider yok"
        value = Decimal(leader["value"])
        display_value = _money(value)
        text = (
            f"Müşteri sıralamasında değişiklik var. Yeni {phrase} müşteri: "
            f"{leader['name']}. Toplam {measure}: {display_value} {unit}. "
            f"Önceki lider: {previous_name}. "
            "Karşılaştırma, rapordaki sevk edilmiş siparişlere dayanır."
        )
        notify_management(
            title,
            text,
            reverse("customer_comparison_report"),
        )
        sent += 1
    return sent


def process_customer_monitor(now=None):
    """Status checked after 09:00; six ranking leaders checked after 20:00 (Istanbul)."""
    local = timezone.localtime(now or timezone.now())
    today = local.date()
    status_due = local.hour >= 9 and not CustomerMonitorState.objects.filter(
        key="customer_status", last_checked_on=today
    ).exists()
    leaders_due = local.hour >= 20 and not CustomerMonitorState.objects.filter(
        key="customer_leaders", last_checked_on=today
    ).exists()
    if not status_due and not leaders_due:
        return {"skipped": "already_checked_or_before_window"}

    # Same shipment selection and finance calculation as the actual comparison report.
    from .customer_report_views import _shipment_finance_rows

    rows = _shipment_finance_rows()
    outcomes = {}
    if status_due:
        statuses = _collect_statuses(rows, today)
        outcomes["statuses"] = _capture_once(
            "customer_status", today, statuses, _notify_status
        )
    if leaders_due:
        leaders = _collect_leaders(rows)
        outcomes["leaders"] = _capture_once(
            "customer_leaders", today, leaders, _notify_leaders
        )
    return outcomes
