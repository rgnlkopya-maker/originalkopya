from decimal import Decimal

from django.db import migrations


def money2(value):
    return value.quantize(Decimal("0.01")) if value is not None else None


def to_try(amount, currency, usd_try):
    if amount is None:
        return None
    amount = Decimal(amount)
    if currency == "USD":
        return amount * usd_try if usd_try else None
    return amount


def repair_snapshots(apps, schema_editor):
    Order = apps.get_model("core", "Order")
    ProductCost = apps.get_model("core", "ProductCost")
    ExchangeRate = apps.get_model("product_cards", "ExchangeRate")
    OrderFinancialSnapshot = apps.get_model("product_cards", "OrderFinancialSnapshot")

    rate = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = rate.usd_try if rate else None

    for order in Order.objects.all().iterator():
        snapshot = OrderFinancialSnapshot.objects.filter(order_id=order.id).first()
        if snapshot is None:
            continue

        incomplete = (
            snapshot.satis_tl is None
            or Decimal(snapshot.satis_tl or 0) == 0
            or snapshot.maliyet_tl is None
            or snapshot.beklenen_kar_tl is None
        )
        if not incomplete:
            continue

        sale = Decimal(order.satis_fiyati or 0)
        if sale <= 0:
            continue
        sale_currency = order.para_birimi or "TRY"
        sale_tl = to_try(sale, sale_currency, snapshot.usd_try or usd_try)

        product_cost = ProductCost.objects.filter(
            urun_kodu__iexact=(order.urun_kodu or ""),
            is_active=True,
        ).first()

        cost = None
        cost_currency = order.maliyet_para_birimi or "TRY"
        if order.maliyet_override is not None:
            cost = Decimal(order.maliyet_override)
        elif product_cost is not None:
            cost = Decimal(product_cost.maliyet)
            cost_currency = product_cost.para_birimi or "TRY"
            if order.maliyet_uygulanan is None or Decimal(order.maliyet_uygulanan or 0) == 0:
                Order.objects.filter(pk=order.pk).update(
                    maliyet_uygulanan=product_cost.maliyet,
                    maliyet_para_birimi=cost_currency,
                )
        elif order.maliyet_uygulanan is not None and Decimal(order.maliyet_uygulanan or 0) != 0:
            cost = Decimal(order.maliyet_uygulanan)

        if cost is None:
            continue

        effective_cost = cost + Decimal(order.ekstra_maliyet or 0)
        rate_value = snapshot.usd_try or usd_try
        cost_tl = to_try(effective_cost, cost_currency, rate_value)
        if sale_tl is None or cost_tl is None:
            continue

        profit = sale_tl - cost_tl
        profit_rate = (profit / sale_tl * Decimal("100")) if sale_tl else None

        snapshot.usd_try = rate_value
        snapshot.satis_fiyati = sale
        snapshot.satis_para_birimi = sale_currency
        snapshot.satis_tl = money2(sale_tl)
        snapshot.maliyet_tl = money2(cost_tl)
        snapshot.beklenen_kar_tl = money2(profit)
        snapshot.beklenen_kar_orani = money2(profit_rate)
        snapshot.save(update_fields=[
            "usd_try",
            "satis_fiyati",
            "satis_para_birimi",
            "satis_tl",
            "maliyet_tl",
            "beklenen_kar_tl",
            "beklenen_kar_orani",
        ])


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0013_warehouse_stock"),
    ]

    operations = [
        migrations.RunPython(repair_snapshots, migrations.RunPython.noop),
    ]
