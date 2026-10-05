import os
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db import migrations


def seed_eylus_demo_folios_and_orders(apps, schema_editor):
    if os.getenv("DEMO_MODE") != "1":
        return

    User = apps.get_model("auth", "User")
    Musteri = apps.get_model("core", "Musteri")
    ProductCost = apps.get_model("core", "ProductCost")
    Order = apps.get_model("core", "Order")
    ProductCard = apps.get_model("product_cards", "ProductCard")
    ShowroomDraft = apps.get_model("product_cards", "ShowroomDraft")
    ShowroomDraftItem = apps.get_model("product_cards", "ShowroomDraftItem")
    ShowroomOrderLink = apps.get_model("product_cards", "ShowroomOrderLink")
    ShowroomPayment = apps.get_model("product_cards", "ShowroomPayment")

    marker = "EYLUS-DEMO-50"
    if ShowroomDraft.objects.filter(order_taken_by__startswith=marker).exists():
        return

    creator = User.objects.filter(username="demo").first() or User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not creator:
        return

    customers = list(Musteri.objects.filter(aktif=True).order_by("id")[:20])
    cards = list(ProductCard.objects.select_related("urun").filter(urun__kod__startswith="DM-").order_by("urun__kod")[:30])
    if not customers or not cards:
        return

    colors = ["Ekru", "Beyaz", "Siyah", "Pudra", "Lacivert", "Bordo", "Gül Kurusu", "Zeytin"]
    sizes = ["34", "36", "38", "40", "42", "44", "46", "48"]
    discount_rates = [Decimal("0"), Decimal("5"), Decimal("7.5"), Decimal("10"), Decimal("12")]
    vat_rates = [Decimal("10"), Decimal("20")]
    order_types = ["SERI", "OZEL", "TEKLI"]
    methods = ["CASH", "CARD", "CHECK", "NOTE"]
    today = date(2026, 10, 4)

    next_numbers = {}
    for order_type in ["SERI", "OZEL", "TEKLI"]:
        prefix = "OZEL" if order_type == "OZEL" else order_type
        max_num = 0
        for existing in Order.objects.filter(siparis_tipi=order_type).exclude(siparis_numarasi="").values_list("siparis_numarasi", flat=True):
            digits = "".join(ch for ch in (existing or "") if ch.isdigit())
            if digits:
                try:
                    max_num = max(max_num, int(digits))
                except ValueError:
                    pass
        next_numbers[order_type] = max_num + 1

    for i in range(50):
        customer = customers[i % len(customers)]
        card = cards[(i * 7) % len(cards)]
        code = card.urun.kod
        pcost = ProductCost.objects.filter(urun_kodu__iexact=code).first()
        cost = Decimal(pcost.maliyet or 0) if pcost else Decimal("0")

        # Maliyetin uzerine degisen karlilik; yuvarlak ve sunumda dogal fiyatlar.
        margin = [Decimal("1.38"), Decimal("1.45"), Decimal("1.52"), Decimal("1.60")][i % 4]
        base_price = (cost * margin).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if base_price <= 0:
            base_price = Decimal("12000") + Decimal((i % 8) * 500)

        discount = discount_rates[i % len(discount_rates)]
        vat = vat_rates[i % len(vat_rates)]
        delivery = today + timedelta(days=18 + (i % 43))
        previous_balance = Decimal("0") if i % 4 else Decimal(500 + (i % 6) * 250)

        pricing_ops = []
        if discount > 0:
            pricing_ops.append({"type":"DISCOUNT","mode":"PERCENT","value":str(discount)})
        pricing_ops.append({"type":"VAT","mode":"PERCENT","value":str(vat)})

        draft = ShowroomDraft.objects.create(
            created_by=creator,
            customer=customer,
            order_taken_by=f"{marker} / Demo Patron",
            delivery_date=delivery,
            order_type=order_types[i % len(order_types)],
            status="TRANSFERRED",
            currency="TRY",
            profit_rate=Decimal("0"),
            discount_rate=discount,
            monthly_term_rate=Decimal("0"),
            usd_try=Decimal("1"),
            eur_try=Decimal("1"),
            gbp_try=Decimal("1"),
            overall_discount_amount=Decimal("0"),
            vat_rate=vat,
            previous_balance=previous_balance,
            pricing_operations=pricing_ops,
            orders_created=True,
        )

        item = ShowroomDraftItem.objects.create(
            draft=draft,
            product_card=card,
            color=colors[(i * 3) % len(colors)],
            size=sizes[(i * 5) % len(sizes)],
            description=["Standart üretim", "Aksesuar kontrolü", "Öncelikli teslim", "Müşteri özel seçimi", "Showroom siparişi"][i % 5],
            quantity=1,
            unit_price=base_price,
            discount_selected=True,
        )

        net_price = base_price
        if discount > 0:
            net_price = net_price * (Decimal("1") - discount / Decimal("100"))
        net_price = net_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        order_type = draft.order_type
        prefix = "OZEL" if order_type == "OZEL" else order_type
        order_number = f"{prefix}{next_numbers[order_type]:04d}"
        while Order.objects.filter(siparis_numarasi=order_number).exists():
            next_numbers[order_type] += 1
            order_number = f"{prefix}{next_numbers[order_type]:04d}"
        next_numbers[order_type] += 1

        order = Order.objects.create(
            siparis_tipi=order_type,
            siparis_numarasi=order_number,
            musteri=customer,
            urun_kodu=code,
            urun_tipi=getattr(card.urun, "urun_tipi", "") or "",
            renk=item.color,
            beden=item.size,
            teslim_tarihi=delivery,
            adet=1,
            aciklama=item.description,
            satis_fiyati=net_price,
            vat_rate=vat,
            para_birimi="TRY",
            maliyet_uygulanan=cost,
            maliyet_para_birimi=(pcost.para_birimi if pcost else "TRY"),
        )

        ShowroomOrderLink.objects.create(
            draft=draft,
            draft_item=item,
            order=order,
            order_number=order.siparis_numarasi or "",
        )

        # Her foye bir finans hareketi: yarisi tahsilat, yarisi odeme sozu.
        gross = (net_price * (Decimal("1") + vat / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        amount = (gross * [Decimal("0.20"), Decimal("0.30"), Decimal("0.40"), Decimal("0.50")][i % 4]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if i % 2 == 0:
            ShowroomPayment.objects.create(
                draft=draft,
                entry_type="COLLECTION",
                method=methods[i % len(methods)],
                amount=amount,
                payment_date=today - timedelta(days=i % 6),
                note="Demo kapora / tahsilat",
            )
        else:
            ShowroomPayment.objects.create(
                draft=draft,
                entry_type="PROMISE",
                method=methods[i % len(methods)],
                amount=amount,
                due_date=today + timedelta(days=7 + (i % 30)),
                note="Demo ödeme planı",
            )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0037_showroomdraft_delivery_date"),
        ("core", "0080_realistic_eylus_demo_leave_history"),
    ]

    operations = [
        migrations.RunPython(seed_eylus_demo_folios_and_orders, migrations.RunPython.noop),
    ]
