from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order, ProductCost, UrunKod
from .models import ExchangeRate, OrderFinancialSnapshot, ProductCard, ShipmentFinancialSnapshot, amount_to_try


@receiver(post_save, sender=UrunKod)
def ensure_product_card(sender, instance, **kwargs):
    ProductCard.objects.get_or_create(urun=instance)


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
    sale_tl = amount_to_try(sale, sale_currency, usd_try)

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
        effective_cost = cost + Decimal(instance.ekstra_maliyet or 0)
        cost_tl = amount_to_try(effective_cost, cost_currency, usd_try)

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
    sale_tl = amount_to_try(sale, sale_currency, conversion_rate)
    shipped = ShipmentFinancialSnapshot.objects.filter(order=instance).exists()

    if shipped:
        # Sevkiyat sonrası maliyet snapshot'i kilitli kalir.
        # Satış fiyatı ise sipariş detayında manuel düzeltildiyse sevkiyat finansının
        # baz satışını da aynı değere taşı. Finans hareketleri bunun üzerine uygulanır.
        shipment_snapshot = ShipmentFinancialSnapshot.objects.filter(order=instance).first()
        if shipment_snapshot is not None:
            shipment_cost_tl = Decimal(shipment_snapshot.toplam_maliyet_tl or 0)
            shipment_profit = sale_tl - shipment_cost_tl if sale_tl is not None else None
            shipment_profit_rate = (
                shipment_profit / sale_tl * Decimal("100")
                if shipment_profit is not None and sale_tl
                else None
            )
            shipment_snapshot.satis_fiyati = sale
            shipment_snapshot.satis_para_birimi = sale_currency
            shipment_snapshot.satis_tl = _money2(sale_tl)
            shipment_snapshot.gerceklesen_kar_tl = _money2(shipment_profit)
            shipment_snapshot.gerceklesen_kar_orani = _money2(shipment_profit_rate)
            shipment_snapshot.save(update_fields=[
                "satis_fiyati",
                "satis_para_birimi",
                "satis_tl",
                "gerceklesen_kar_tl",
                "gerceklesen_kar_orani",
            ])
        cost_tl = Decimal(snapshot.maliyet_tl) if snapshot.maliyet_tl is not None else None
    elif cost is not None:
        effective_cost = cost + Decimal(instance.ekstra_maliyet or 0)
        cost_tl = amount_to_try(effective_cost, cost_currency, conversion_rate)

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
