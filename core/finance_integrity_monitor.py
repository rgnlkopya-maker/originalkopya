"""Notify managers only when a shipped order develops a financial data error.

Read-only audit of the same shipped-order population as Sevkiyat Finans.
Persistent per-order issue keys suppress repeats until that particular problem
has disappeared and reappeared. There is no daily health-summary notification.
"""
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import DateTimeField, OuterRef, Prefetch, Subquery
from django.urls import reverse
from django.utils import timezone

from product_cards.finance_views import (
    FINANCIAL_MOVEMENT_LABELS, LEGACY_OPERATION_LABELS, calculate_finance_result,
)

from .models import CustomerMonitorState, Order, OrderEvent

logger = logging.getLogger(__name__)

INTERVAL = timedelta(minutes=5)
MAX_NOTIFICATIONS_PER_SCAN = 20
STATE_KEY = "finance_integrity"
FINANCE_STAGES = ["satis_fiyati", "ekstra_maliyet", "maliyet_override", "maliyet_uygulanan"]
KNOWN_MOVEMENTS = set(FINANCIAL_MOVEMENT_LABELS) | set(LEGACY_OPERATION_LABELS)
CENT = Decimal("0.01")


def shipped_finance_orders():
    """Exactly match the shipped-order selection used by Sevkiyat Finans."""
    latest = (
        OrderEvent.objects.filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")
        .exclude(stage__in=FINANCE_STAGES)
        .order_by("-id")[:1]
    )
    return (
        Order.objects.select_related("musteri", "shipment_financial_snapshot")
        .prefetch_related(Prefetch(
            "events",
            queryset=OrderEvent.objects.filter(
                stage__in=["finans_hareketi", "sevkiyat_durum"]
            ).order_by("timestamp", "id"),
            to_attr="_finance_events_prefetched",
        ))
        .annotate(
            latest_stage=Subquery(latest.values("stage")),
            latest_value=Subquery(latest.values("value")),
            last_status_date=Subquery(latest.values("timestamp"), output_field=DateTimeField()),
        )
        .filter(is_active=True, latest_stage="sevkiyat_durum", latest_value="gonderildi")
        .exclude(siparis_tipi="MALZEME")
        .order_by("id")
    )


def _issue(issues, order, code, detail):
    key = f"{order.pk}:{code}"
    customer = order.musteri.ad if order.musteri_id else "Stok"
    issues[key] = {
        "order_id": order.pk,
        "order_number": order.siparis_numarasi,
        "customer": customer,
        "product": order.urun_kodu or "Belirtilmemiş",
        "detail": detail,
        "type": code,
    }


def audit_financial_order(order):
    """Use independent snapshot invariants; never repair or modify money."""
    issues = {}
    snapshot = getattr(order, "shipment_financial_snapshot", None)
    if snapshot is None:
        _issue(issues, order, "snapshot_missing", "Sevkiyat finans kaydı oluşturulmamış.")
        return issues

    if order.satis_fiyati is None:
        _issue(issues, order, "sale_missing", "Sipariş satış fiyatı boş.")
    if snapshot.satis_tl is None:
        _issue(issues, order, "sale_tl_missing", "Sevkiyat satışının TL karşılığı boş.")
    if snapshot.toplam_maliyet_tl is None:
        _issue(issues, order, "cost_missing", "Kesinleşmiş sevkiyat maliyeti hesaplanamamış.")
    elif snapshot.toplam_maliyet_tl < 0:
        _issue(issues, order, "cost_negative", "Sevkiyat maliyeti negatif olamaz.")

    currency = (order.para_birimi or "TRY").upper()
    if currency == "USD" and (snapshot.usd_try is None or snapshot.usd_try <= 0):
        _issue(issues, order, "usd_rate_missing", "USD sevkiyatının geçerli döviz kuru yok.")
    if (
        currency == "USD" and order.satis_fiyati is not None
        and snapshot.usd_try is not None and snapshot.usd_try > 0
        and snapshot.satis_tl is not None
    ):
        expected = Decimal(order.satis_fiyati) * Decimal(snapshot.usd_try)
        if abs(expected - Decimal(snapshot.satis_tl)) > CENT:
            _issue(
                issues, order, "usd_conversion_mismatch",
                f"USD satış dönüşümü uyuşmuyor: {order.satis_fiyati} USD × "
                f"{snapshot.usd_try}, kayıtlı tutar {snapshot.satis_tl} TL. "
                "Finans hareketleri bu temel sevkiyat tutarından sonra uygulanır.",
            )

    if snapshot.satis_tl is not None and snapshot.toplam_maliyet_tl is not None:
        expected_profit = Decimal(snapshot.satis_tl) - Decimal(snapshot.toplam_maliyet_tl)
        if snapshot.gerceklesen_kar_tl is None:
            _issue(issues, order, "snapshot_profit_missing", "Sevkiyat kâr kaydı boş.")
        elif abs(expected_profit - Decimal(snapshot.gerceklesen_kar_tl)) > CENT:
            _issue(
                issues, order, "snapshot_profit_mismatch",
                "Sevkiyat kaydındaki kâr, kayıtlı satış eksi maliyet hesabıyla uyuşmuyor.",
            )

    events = getattr(order, "_finance_events_prefetched", None)
    if events is None:
        events = order.events.filter(
            stage__in=["finans_hareketi", "sevkiyat_durum"]
        ).order_by("timestamp", "id")
    for event in events:
        if event.stage != "finans_hareketi":
            continue
        if event.value not in KNOWN_MOVEMENTS:
            _issue(
                issues, order, f"unknown_movement_{event.pk}",
                f"Tanımlanmamış finans hareketi ({event.value}) var. "
                "Bu hareket kesinleşmiş hesapta işlenmiyor olabilir.",
            )
            continue
        try:
            data = json.loads(event.new_value or "")
            amount = Decimal(str(data["tl_amount"]))
            if not isinstance(data, dict) or not amount.is_finite() or amount < 0:
                raise ValueError("invalid amount")
        except (ValueError, InvalidOperation, KeyError, TypeError, AttributeError):
            _issue(
                issues, order, f"invalid_movement_{event.pk}",
                f"Finans hareketinin TL tutarı eksik veya hatalı ({event.value}).",
            )

    try:
        result = calculate_finance_result(order)
    except (ValueError, InvalidOperation, TypeError, ArithmeticError, AttributeError) as exc:
        _issue(
            issues, order, "calculation_failed",
            f"Sevkiyat finans hesaplaması başarısız: {type(exc).__name__}.",
        )
        return issues

    if result.get("is_final") and result.get("satis_tl") is not None and result["satis_tl"] <= 0:
        _issue(
            issues, order, "sale_zero",
            "Kesinleşmiş satış tutarı sıfır. Ücretsiz sevkiyat olabilir; "
            "bilinçli girilip girilmediğini kontrol edin.",
        )
    if result.get("is_final") and result.get("maliyet_tl") is not None and result["maliyet_tl"] < 0:
        _issue(issues, order, "computed_cost_negative", "Hesaplanmış maliyet negatif.")
    return issues


def detect_finance_errors():
    """Full shipped-order scan, independent from a report's cached totals."""
    issues = {}
    for order in shipped_finance_orders():
        try:
            issues.update(audit_financial_order(order))
        except Exception as exc:
            logger.exception("Financial integrity audit failed on order id %s", order.pk)
            _issue(
                issues, order, "audit_failed",
                f"Finans veri kontrolü sipariş için tamamlanamadı: {type(exc).__name__}.",
            )
    return issues


def process_finance_integrity(now=None):
    """Check at most every five minutes; notify only newly appearing errors."""
    checked_at = now or timezone.now()
    from .manager_notification_signals import notify_management

    with transaction.atomic():
        state, created = CustomerMonitorState.objects.select_for_update().get_or_create(
            key=STATE_KEY, defaults={"payload": {"active": []}},
        )
        if not created and state.updated_at > checked_at - INTERVAL:
            return {"skipped": "within_5_minutes"}

        current = detect_finance_errors()
        previous = set(
            state.payload.get("active", [])
            if isinstance(state.payload, dict) else []
        )
        pending = sorted(set(current) - previous)
        new_keys = pending[:MAX_NOTIFICATIONS_PER_SCAN]
        for key in new_keys:
            issue = current[key]
            message = (
                f"{issue['order_number']} | {issue['customer']} | "
                f"Ürün: {issue['product']}. {issue['detail']} "
                "Finans hareketlerini kontrol etmek için bildirime dokunun."
            )
            notify_management(
                "Sevkiyat Finans Veri Hatası",
                message,
                reverse("order_finance_movements", args=[issue["order_id"]]),
            )

        # Keep only current, successfully announced issue keys. A fixed issue
        # is removed and will trigger again if it reappears in a later scan.
        state.payload = {
            "active": sorted((previous & set(current)) | set(new_keys)),
            "total_open": len(current),
        }
        state.last_checked_on = timezone.localdate(checked_at)
        state.save(update_fields=["payload", "last_checked_on", "updated_at"])
        if now is not None:
            # Deterministic time source for tests; normal scheduler uses auto_now.
            CustomerMonitorState.objects.filter(pk=state.pk).update(updated_at=checked_at)

    return {
        "open_issues": len(current),
        "new_notifications": len(new_keys),
        "pending": len(pending) - len(new_keys),
    }
