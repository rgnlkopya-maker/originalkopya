from decimal import Decimal

from django.db import migrations


def _money2(value):
    return value.quantize(Decimal("0.01")) if value is not None else None


def _to_try(amount, currency, usd_try):
    if amount is None:
        return None
    amount = Decimal(amount)
    if currency == "USD":
        return amount * Decimal(usd_try) if usd_try else None
    return amount


def sync_existing_shipment_finance(apps, schema_editor):
    Order = apps.get_model("core", "Order")
    ProductCost = apps.get_model("core", "ProductCost")
    ShipmentFinancialSnapshot = apps.get_model("product_cards", "ShipmentFinancialSnapshot")

    snapshots = ShipmentFinancialSnapshot.objects.select_related("order").all()

    for snapshot in snapshots.iterator():
        order = snapshot.order
        rate = snapshot.usd_try

        sale = Decimal(order.satis_fiyati or 0)
        sale_currency = order.para_birimi or "TRY"
        sale_tl = _to_try(sale, sale_currency, rate)

        product_cost = (
            ProductCost.objects.filter(
                urun_kodu__iexact=(order.urun_kodu or ""),
                is_active=True,
            )
            .order_by("id")
            .first()
        )

        cost = None
        cost_currency = order.maliyet_para_birimi or "TRY"
        if order.maliyet_override is not None:
            cost = Decimal(order.maliyet_override)
        elif product_cost is not None:
            cost = Decimal(product_cost.maliyet)
            cost_currency = product_cost.para_birimi or "TRY"
        elif order.maliyet_uygulanan is not None:
            cost = Decimal(order.maliyet_uygulanan)

        base_cost_tl = _to_try(cost, cost_currency, rate) if cost is not None else None
        extra_cost_tl = (
            _to_try(Decimal(order.ekstra_maliyet or 0), cost_currency, rate)
            or Decimal("0")
        )
        total_cost_tl = (
            base_cost_tl + extra_cost_tl if base_cost_tl is not None else None
        )
        profit = (
            sale_tl - total_cost_tl
            if sale_tl is not None and total_cost_tl is not None
            else None
        )
        profit_rate = (
            profit / sale_tl * Decimal("100")
            if profit is not None and sale_tl
            else None
        )

        snapshot.satis_fiyati = sale
        snapshot.satis_para_birimi = sale_currency
        snapshot.satis_tl = _money2(sale_tl)
        snapshot.urun_maliyeti_tl = _money2(base_cost_tl)
        snapshot.sevkiyat_ekstra_maliyet_tl = _money2(extra_cost_tl) or Decimal("0.00")
        snapshot.toplam_maliyet_tl = _money2(total_cost_tl)
        snapshot.gerceklesen_kar_tl = _money2(profit)
        snapshot.gerceklesen_kar_orani = _money2(profit_rate)
        snapshot.save(update_fields=[
            "satis_fiyati",
            "satis_para_birimi",
            "satis_tl",
            "urun_maliyeti_tl",
            "sevkiyat_ekstra_maliyet_tl",
            "toplam_maliyet_tl",
            "gerceklesen_kar_tl",
            "gerceklesen_kar_orani",
        ])


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0032_sync_podyum_maras_prices"),
    ]

    operations = [
        migrations.RunPython(sync_existing_shipment_finance, migrations.RunPython.noop),
    ]
