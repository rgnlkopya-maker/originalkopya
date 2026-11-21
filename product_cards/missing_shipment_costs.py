"""Fill only missing shipment costs; never reprice completed shipments."""
from decimal import Decimal

from django.db import transaction

from core.models import OrderEvent, ProductCost
from .models import ShipmentFinancialSnapshot, amount_to_try


def fill_missing_shipment_costs(product_code=None, *, apply=True):
    """Return eligible shipment count, optionally writing missing base costs.

    Existing nonzero costs, order overrides and manually finalized costs are immutable.
    Conversion uses the exchange rate stored at shipment, never today's rate.
    """
    qs = ShipmentFinancialSnapshot.objects.select_related("order").filter(
        urun_maliyeti_tl__isnull=True,
    ) | ShipmentFinancialSnapshot.objects.select_related("order").filter(
        urun_maliyeti_tl=Decimal("0"),
    )
    if product_code is not None:
        qs = qs.filter(order__urun_kodu__iexact=product_code)
    repaired = 0
    for item in qs.order_by("pk").iterator():
        with transaction.atomic():
            snapshot = ShipmentFinancialSnapshot.objects.select_for_update().select_related("order").get(pk=item.pk)
            order = snapshot.order
            if snapshot.urun_maliyeti_tl not in (None, Decimal("0")):
                continue
            if snapshot.toplam_maliyet_tl not in (None, Decimal("0")):
                continue
            if order.maliyet_override is not None:
                continue
            if OrderEvent.objects.filter(order=order, stage="finans_hareketi", value="NIHAI_MALIYET").exists():
                continue
            product_cost = ProductCost.objects.filter(
                urun_kodu__iexact=order.urun_kodu or "", is_active=True
            ).order_by("pk").first()
            if product_cost is None or Decimal(product_cost.maliyet or 0) <= 0:
                continue
            base = amount_to_try(Decimal(product_cost.maliyet), product_cost.para_birimi or "TRY", snapshot.usd_try)
            if base is None or base <= 0:
                continue
            # Do not overwrite shipments that recorded nonzero extras or discounts.
            if Decimal(order.ekstra_maliyet or 0) != 0 or Decimal(order.maliyet_indirimi or 0) != 0:
                continue
            if Decimal(snapshot.sevkiyat_ekstra_maliyet_tl or 0) != 0:
                continue
            base = base.quantize(Decimal("0.01"))
            profit = (Decimal(snapshot.satis_tl) - base) if snapshot.satis_tl is not None else None
            rate = (profit / Decimal(snapshot.satis_tl) * 100) if profit is not None and snapshot.satis_tl else None
            if apply:
                snapshot.urun_maliyeti_tl = base
                snapshot.toplam_maliyet_tl = base
                snapshot.gerceklesen_kar_tl = profit.quantize(Decimal("0.01")) if profit is not None else None
                snapshot.gerceklesen_kar_orani = rate.quantize(Decimal("0.01")) if rate is not None else None
                snapshot.save(update_fields=[
                    "urun_maliyeti_tl", "toplam_maliyet_tl",
                    "gerceklesen_kar_tl", "gerceklesen_kar_orani",
                ])
            repaired += 1
    return repaired
