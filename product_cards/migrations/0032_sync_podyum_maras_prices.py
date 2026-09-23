from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


DRAFT_ID = 71


def sync_podyum_prices(apps, schema_editor):
    Draft = apps.get_model("product_cards", "ShowroomDraft")
    DraftItem = apps.get_model("product_cards", "ShowroomDraftItem")
    Link = apps.get_model("product_cards", "ShowroomOrderLink")
    OrderFinancialSnapshot = apps.get_model("product_cards", "OrderFinancialSnapshot")
    ShipmentFinancialSnapshot = apps.get_model("product_cards", "ShipmentFinancialSnapshot")

    draft = Draft.objects.filter(id=DRAFT_ID).first()
    if not draft:
        return

    items = list(
        DraftItem.objects
        .filter(draft_id=DRAFT_ID)
        .select_related("product_card__urun")
        .order_by("product_card__urun__kod", "color", "size", "id")
    )
    links = list(
        Link.objects
        .filter(draft_id=DRAFT_ID, order_id__isnull=False)
        .select_related("order")
        .order_by("id")
    )
    if not items or not links:
        return

    subtotal = sum(
        (Decimal(item.unit_price or 0) * Decimal(max(1, int(item.quantity or 1))) for item in items),
        Decimal("0"),
    )

    current = subtotal
    vat_multiplier = Decimal("1")
    for op in (draft.pricing_operations or []):
        op_type = str(op.get("type") or "").upper()
        mode = str(op.get("mode") or "").upper()
        value = Decimal(str(op.get("value") or 0))
        if op_type == "DISCOUNT":
            if mode == "PERCENT":
                current -= current * value / Decimal("100")
            else:
                current -= min(current, value)
        elif op_type == "VAT":
            current += current * value / Decimal("100")
            vat_multiplier *= Decimal("1") + (value / Decimal("100"))

    if draft.folio_adjustment_target is not None:
        current = Decimal(draft.folio_adjustment_target)

    net_target_total = current / vat_multiplier if vat_multiplier > 0 else current
    vat_rate = ((vat_multiplier - Decimal("1")) * Decimal("100")).quantize(Decimal("0.01"))

    unit_rows = []
    for item in items:
        for _ in range(max(1, int(item.quantity or 1))):
            unit_rows.append(item)

    allocated = []
    allocated_total = Decimal("0")
    factor = (net_target_total / subtotal) if subtotal > 0 else Decimal("0")
    for idx, item in enumerate(unit_rows):
        if idx == len(unit_rows) - 1:
            price = max(Decimal("0"), net_target_total - allocated_total)
        else:
            price = (Decimal(item.unit_price or 0) * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            allocated_total += price
        allocated.append((item, price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))

    price_groups = defaultdict(list)
    for item, price in allocated:
        key = (item.product_card.urun.kod or "", item.color or "", item.size or "")
        price_groups[key].append(price)

    link_groups = defaultdict(list)
    for link in links:
        order = link.order
        key = (order.urun_kodu or "", order.renk or "", order.beden or "")
        link_groups[key].append(link)

    for key, group_links in link_groups.items():
        prices = price_groups.get(key, [])
        if len(prices) != len(group_links):
            continue
        for link, price in zip(group_links, prices):
            order = link.order
            order.satis_fiyati = price
            order.vat_rate = vat_rate
            order.save(update_fields=["satis_fiyati", "vat_rate", "last_updated"])

            ofs = OrderFinancialSnapshot.objects.filter(order_id=order.id).first()
            if ofs:
                sale_tl = price * Decimal(ofs.usd_try) if (order.para_birimi or "TRY") == "USD" and ofs.usd_try else price
                profit = sale_tl - Decimal(ofs.maliyet_tl) if ofs.maliyet_tl is not None else None
                profit_rate = profit / sale_tl * Decimal("100") if profit is not None and sale_tl else None
                ofs.satis_fiyati = price
                ofs.satis_para_birimi = order.para_birimi or "TRY"
                ofs.satis_tl = sale_tl.quantize(Decimal("0.01"))
                ofs.beklenen_kar_tl = profit.quantize(Decimal("0.01")) if profit is not None else None
                ofs.beklenen_kar_orani = profit_rate.quantize(Decimal("0.01")) if profit_rate is not None else None
                ofs.save(update_fields=["satis_fiyati","satis_para_birimi","satis_tl","beklenen_kar_tl","beklenen_kar_orani"])

            sfs = ShipmentFinancialSnapshot.objects.filter(order_id=order.id).first()
            if sfs:
                sale_tl = price * Decimal(sfs.usd_try) if (order.para_birimi or "TRY") == "USD" and sfs.usd_try else price
                profit = sale_tl - Decimal(sfs.toplam_maliyet_tl) if sfs.toplam_maliyet_tl is not None else None
                profit_rate = profit / sale_tl * Decimal("100") if profit is not None and sale_tl else None
                sfs.satis_fiyati = price
                sfs.satis_para_birimi = order.para_birimi or "TRY"
                sfs.satis_tl = sale_tl.quantize(Decimal("0.01"))
                sfs.gerceklesen_kar_tl = profit.quantize(Decimal("0.01")) if profit is not None else None
                sfs.gerceklesen_kar_orani = profit_rate.quantize(Decimal("0.01")) if profit_rate is not None else None
                sfs.save(update_fields=["satis_fiyati","satis_para_birimi","satis_tl","gerceklesen_kar_tl","gerceklesen_kar_orani"])


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0031_repair_podyum_maras_links"),
    ]

    operations = [
        migrations.RunPython(sync_podyum_prices, migrations.RunPython.noop),
    ]
