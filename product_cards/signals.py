from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order, ProductCost, UrunKod
from .models import ExchangeRate, OrderFinancialSnapshot, ProductCard, ShipmentFinancialSnapshot, amount_to_try


@receiver(post_save, sender=UrunKod)
def ensure_product_card(sender, instance, **kwargs):
    ProductCard.objects.get_or_create(urun=instance)


def _convert_to_try(amount, currency, usd_rate, rates):
    """Convert an order amount using the corresponding exchange rate."""
    if amount is None:
        return None
    currency = (currency or "TRY").upper()
    if currency == "TRY":
        return Decimal(amount)
    rate = usd_rate if currency == "USD" else getattr(rates, currency.lower() + "_try", None) if currency in ("EUR", "GBP") else None
    return Decimal(amount) * Decimal(rate) if rate and Decimal(rate) > 0 else None


def _money2(value):
    return value.quantize(Decimal("0.01")) if value is not None else None


@receiver(post_save, sender=Order)
def sync_order_financial_snapshot(sender, instance, created, **kwargs):
    """Keep the detail-page finance summary in sync with the current order price.

    Product cost continues to follow the active cost until shipment. After shipment only
    the cost stays frozen; later sale-price edits still refresh the displayed price/profit.
    """
    rate_obj = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = rate_obj.usd_try if rate_obj else None

    sale = Decimal(instance.satis_fiyati or 0)
    sale_currency = instance.para_birimi or "TRY"
    sale_tl = _convert_to_try(sale, sale_currency, usd_try, rate_obj)

    product_cost = ProductCost.objects.filter(
        urun_kodu__iexact=(instance.urun_kodu or ""),
        is_active=True,
    ).first()

    cost = None
    cost_currency = instance.maliyet_para_birimi or "TRY"
    if instance.maliyet_override is not None:
        cost = Decimal(instance.maliyet_override)
    elif product_cost is not None:
        cost = Decimal(product_cost.maliyet)
        cost_currency = product_cost.para_birimi or "TRY"
        if instance.maliyet_uygulanan is None or Decimal(instance.maliyet_uygulanan or 0) == 0:
            Order.objects.filter(pk=instance.pk).update(
                maliyet_uygulanan=product_cost.maliyet,
                maliyet_para_birimi=cost_currency,
            )
    elif instance.maliyet_uygulanan is not None and Decimal(instance.maliyet_uygulanan or 0) != 0:
        cost = Decimal(instance.maliyet_uygulanan)

    cost_tl = None
    if cost is not None:
        effective_cost = max(Decimal("0"), cost + Decimal(instance.ekstra_maliyet or 0) - Decimal(instance.maliyet_indirimi or 0))
        cost_tl = _convert_to_try(effective_cost, cost_currency, usd_try, rate_obj)

    profit = sale_tl - cost_tl if sale_tl is not None and cost_tl is not None else None
    profit_rate = (profit / sale_tl * Decimal("100")) if profit is not None and sale_tl else None

    snapshot, was_created = OrderFinancialSnapshot.objects.get_or_create(
        order=instance,
        defaults={
            "usd_try": usd_try,
            "satis_fiyati": sale,
            "satis_para_birimi": sale_currency,
            "satis_tl": _money2(sale_tl),
            "maliyet_tl": _money2(cost_tl),
            "beklenen_kar_tl": _money2(profit),
            "beklenen_kar_orani": _money2(profit_rate),
        },
    )
    # Snapshot yeni oluşmuş olsa bile devam et. Sipariş daha önce sevk edildiyse
    # ShipmentFinancialSnapshot satış tarafı da aynı kayıtta senkronlanmalıdır.
    snapshot.usd_try = snapshot.usd_try or usd_try
    conversion_rate = snapshot.usd_try or usd_try
    sale_tl = _convert_to_try(sale, sale_currency, conversion_rate, rate_obj)
    shipped = ShipmentFinancialSnapshot.objects.filter(order=instance).exists()

    if shipped:
        # Sevk edilmiş siparişlerde de satış ve maliyet güncel sipariş verisini izler.
        # Finans hareketleri bu baz değerlerin üzerine uygulanır.
        shipment_snapshot = ShipmentFinancialSnapshot.objects.filter(order=instance).first()
        if shipment_snapshot is not None:
            shipment_rate = shipment_snapshot.usd_try or conversion_rate

            shipment_sale_tl = _convert_to_try(sale, sale_currency, shipment_rate, rate_obj)

            base_cost_tl = None
            extra_cost_tl = Decimal("0")
            if cost is not None:
                base_cost_tl = _convert_to_try(cost, cost_currency, shipment_rate, rate_obj)
                extra_cost_tl = (
                    _convert_to_try(
                        Decimal(instance.ekstra_maliyet or 0),
                        cost_currency,
                        shipment_rate,
                        rate_obj,
                    )
                    or Decimal("0")
                )
                discount_tl = (
                    _convert_to_try(
                        Decimal(instance.maliyet_indirimi or 0),
                        cost_currency,
                        shipment_rate,
                        rate_obj,
                    )
                    or Decimal("0")
                )
            shipment_total_cost_tl = (
                max(Decimal("0"), base_cost_tl + extra_cost_tl - discount_tl)
                if base_cost_tl is not None
                else None
            )

            shipment_profit = (
                shipment_sale_tl - shipment_total_cost_tl
                if shipment_sale_tl is not None and shipment_total_cost_tl is not None
                else None
            )
            shipment_profit_rate = (
                shipment_profit / shipment_sale_tl * Decimal("100")
                if shipment_profit is not None and shipment_sale_tl
                else None
            )

            shipment_snapshot.satis_fiyati = sale
            shipment_snapshot.satis_para_birimi = sale_currency
            shipment_snapshot.satis_tl = _money2(shipment_sale_tl)
            shipment_snapshot.urun_maliyeti_tl = _money2(base_cost_tl)
            shipment_snapshot.sevkiyat_ekstra_maliyet_tl = _money2(extra_cost_tl) or Decimal("0.00")
            shipment_snapshot.toplam_maliyet_tl = _money2(shipment_total_cost_tl)
            shipment_snapshot.gerceklesen_kar_tl = _money2(shipment_profit)
            shipment_snapshot.gerceklesen_kar_orani = _money2(shipment_profit_rate)
            shipment_snapshot.save(update_fields=[
                "satis_fiyati",
                "satis_para_birimi",
                "satis_tl",
                "urun_maliyeti_tl",
                "sevkiyat_ekstra_maliyet_tl",
                "toplam_maliyet_tl",
                "gerceklesen_kar_tl",
                "gerceklesen_kar_orani",
            ])

            # Sipariş detayındaki finans özeti de aynı güncel maliyeti göstermeli.
            cost_tl = shipment_total_cost_tl
        elif cost is not None:
            effective_cost = max(Decimal("0"), cost + Decimal(instance.ekstra_maliyet or 0) - Decimal(instance.maliyet_indirimi or 0))
            cost_tl = _convert_to_try(effective_cost, cost_currency, conversion_rate, rate_obj)
    elif cost is not None:
        effective_cost = max(Decimal("0"), cost + Decimal(instance.ekstra_maliyet or 0) - Decimal(instance.maliyet_indirimi or 0))
        cost_tl = _convert_to_try(effective_cost, cost_currency, conversion_rate, rate_obj)

    profit = sale_tl - cost_tl if sale_tl is not None and cost_tl is not None else None
    profit_rate = (profit / sale_tl * Decimal("100")) if profit is not None and sale_tl else None

    snapshot.satis_fiyati = sale
    snapshot.satis_para_birimi = sale_currency
    snapshot.satis_tl = _money2(sale_tl)
    snapshot.maliyet_tl = _money2(cost_tl)
    snapshot.beklenen_kar_tl = _money2(profit)
    snapshot.beklenen_kar_orani = _money2(profit_rate)
    snapshot.save(update_fields=[
        "usd_try",
        "satis_fiyati",
        "satis_para_birimi",
        "satis_tl",
        "maliyet_tl",
        "beklenen_kar_tl",
        "beklenen_kar_orani",
    ])


@receiver(post_save, sender=Order)
def sync_unexported_invoice_line_from_order(sender, instance, created, update_fields=None, **kwargs):
    """Keep a local draft invoice aligned with edited order price/VAT.

    Sent or uncertain transfers are immutable: never rewrite external invoice snapshots.
    Queryset.update avoids recursion through the Order save signal.
    """
    if created:
        return
    if update_fields is not None and not {"satis_fiyati", "vat_rate"}.intersection(update_fields):
        return
    from .invoice_models import InvoiceLine, BizimHesapInvoiceTransfer, ParasutInvoiceTransfer
    from django.db.models import Exists, OuterRef
    blocked_bh = BizimHesapInvoiceTransfer.objects.filter(
        invoice_id=OuterRef("invoice_id"), status__in=("SENDING", "SENT", "UNKNOWN")
    )
    blocked_ps = ParasutInvoiceTransfer.objects.filter(
        invoice_id=OuterRef("invoice_id"), status__in=("SENDING", "UNKNOWN")
    )
    line = (InvoiceLine.objects.filter(order_id=instance.pk, invoice__status="DRAFT")
            .annotate(bh_blocked=Exists(blocked_bh), ps_blocked=Exists(blocked_ps))
            .filter(bh_blocked=False, ps_blocked=False))
    changed_invoice_ids = list(line.filter(invoice__parasut_transfer__status="SENT").values_list("invoice_id", flat=True))
    if changed_invoice_ids:
        ParasutInvoiceTransfer.objects.filter(invoice_id__in=changed_invoice_ids).update(needs_sync=True)
    line.update(price=instance.satis_fiyati if instance.satis_fiyati is not None else Decimal("0"),
                vat_rate=instance.vat_rate if instance.vat_rate is not None else Decimal("0"))
