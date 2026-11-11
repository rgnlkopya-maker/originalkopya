"""20:00 Istanbul product-ranking alerts, matching the Product Performance Report."""
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from .customer_monitor_service import _capture_once
from .models import CustomerMonitorState
from .product_report_views import build_product_summary


# Metric, direction, heading, description, and unit.
RANKINGS = {
    "revenue_max": ("revenue", False, "En Yüksek Cirolu Ürün Değişti", "En yüksek ciro", "TL"),
    "revenue_min": ("revenue", True, "En Düşük Cirolu Ürün Değişti", "En düşük ciro", "TL"),
    "cost_max": ("cost", False, "En Yüksek Maliyetli Ürün Değişti", "En yüksek toplam maliyet", "TL"),
    "cost_min": ("cost", True, "En Düşük Maliyetli Ürün Değişti", "En düşük toplam maliyet", "TL"),
    "profit_max": ("profit", False, "En Kârlı Ürün Değişti", "En yüksek toplam kâr", "TL"),
    "profit_min": ("profit", True, "En Düşük Kârlı Ürün Değişti", "En düşük toplam kâr", "TL"),
    "quantity_max": ("quantity", False, "En Fazla Sevk Edilen Ürün Değişti", "En fazla sevk edilen adet", "adet"),
    "quantity_min": ("quantity", True, "En Az Sevk Edilen Ürün Değişti", "En az sevk edilen adet", "adet"),
}


def _display_amount(number, unit):
    value = Decimal(str(number))
    places = 0 if unit == "adet" else 2
    formatted = f"{value:,.{places}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".") + " " + unit


def collect_product_rankings(rows):
    """Use precisely the unfiltered Product Performance Report's grouped values."""
    products, _totals = build_product_summary(rows)
    if not products:
        return {}

    rankings = {}
    for ranking, (field, is_min, _title, _label, _unit) in RANKINGS.items():
        # Stable alphabetical tie-break, never a change due to queryset ordering.
        winner = min(
            products,
            key=lambda item: (
                Decimal(str(item[field])) if is_min else -Decimal(str(item[field])),
                item["code"],
            ),
        )
        rankings[ranking] = {
            "code": winner["code"],
            "value": str(winner[field]),
            "missing_cost": winner["finance_missing"],
        }
    return rankings


def _notify_product_rankings(previous, current):
    from .manager_notification_signals import notify_management

    sent = 0
    destination = reverse("product_performance_report")
    for ranking, (field, is_min, title, label, unit) in RANKINGS.items():
        old = previous.get(ranking)
        new = current.get(ranking)
        if not isinstance(old, dict) or not isinstance(new, dict):
            continue  # First baseline, or no comparable products.
        if old.get("code") == new.get("code"):
            continue
        old_code = old.get("code") or "Bilinmiyor"
        old_value = _display_amount(old.get("value", 0), unit)
        new_value = _display_amount(new["value"], unit)
        text = (
            f"Ürün Performans Raporu'ndaki {label.lower()} sıralaması değişti. "
            f"Önceki ürün: {old_code} ({old_value}). "
            f"Yeni ürün: {new['code']} ({new_value}). "
            "Tüm zamanlardaki sevk edilmiş siparişler karşılaştırıldı. "
            "Detaylar için Ürün Performans Raporu'nu açın."
        )
        if field in ("cost", "profit") and new.get("missing_cost"):
            text += (
                f" Dikkat: Yeni ürüne ait {new['missing_cost']} sevkiyatta "
                "maliyet kaydı eksik; sıralama yanıltıcı olabilir."
            )
        notify_management(title, text, destination)
        sent += 1
    return sent


def process_product_monitor(now=None):
    """Run once per Istanbul calendar day at or after 20:00; first run is baseline."""
    local_now = timezone.localtime(now or timezone.now())
    today = local_now.date()
    if local_now.hour < 20:
        return {"skipped": "before_20"}
    if CustomerMonitorState.objects.filter(
        key="product_leaders", last_checked_on=today
    ).exists():
        return {"skipped": "already_checked"}

    from .customer_report_views import _shipment_finance_rows

    current = collect_product_rankings(_shipment_finance_rows())
    if not current:
        return {"skipped": "no_shipped_products"}

    return _capture_once(
        "product_leaders", today, current, _notify_product_rankings,
    )
