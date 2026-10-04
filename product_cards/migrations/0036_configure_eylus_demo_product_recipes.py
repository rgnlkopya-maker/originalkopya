import os
from decimal import Decimal
from django.db import migrations


def configure_demo_product_cards(apps, schema_editor):
    if os.getenv("DEMO_MODE") != "1":
        return

    ProductCard = apps.get_model("product_cards", "ProductCard")
    Material = apps.get_model("product_cards", "Material")
    ProductMaterial = apps.get_model("product_cards", "ProductMaterial")
    ProductCost = apps.get_model("core", "ProductCost")
    ExchangeRate = apps.get_model("product_cards", "ExchangeRate")

    rate = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    usd_try = Decimal(rate.usd_try) if rate else Decimal("1")

    recipe = [
        ("TUL", Decimal("20.000")),
        ("NAKIS_BONCUK", Decimal("1.000")),
        ("UST_DANTEL", Decimal("2.000")),
        ("LEZ_DANTEL", Decimal("4.000")),
        ("SARF", Decimal("1.000")),
        ("ASTAR", Decimal("4.000")),
        ("BEDEN_TULU", Decimal("1.000")),
    ]

    cards = ProductCard.objects.select_related("urun").filter(urun__kod__startswith="DM-")
    for card in cards:
        card.finansman_maliyeti = Decimal("15.00")
        card.finansman_para_birimi = "USD"
        card.genel_gider = Decimal("80.00")
        card.genel_gider_para_birimi = "TRY"
        card.iscilik_maliyeti = Decimal("20.00")
        card.iscilik_para_birimi = "USD"
        card.paketleme_maliyeti = Decimal("5.00")
        card.paketleme_para_birimi = "USD"
        card.nakis_maliyeti = Decimal("0.00")
        card.nakis_para_birimi = "TRY"
        card.save()

        for suffix, qty in recipe:
            material = Material.objects.get(kod=f"{card.urun.kod}-{suffix}")
            ProductMaterial.objects.update_or_create(
                product_card=card,
                material=material,
                defaults={
                    "miktar": qty,
                    "kullanim_asamasi": material.kullanim_asamasi,
                    "notlar": "EYLUS demo urun recetesi",
                },
            )

        material_total = Decimal("0")
        for usage in ProductMaterial.objects.filter(product_card=card).select_related("material"):
            unit_cost = Decimal(usage.material.birim_maliyet or 0)
            if usage.material.birim_maliyet_para_birimi == "USD":
                unit_cost *= usd_try
            material_total += Decimal(usage.miktar) * unit_cost

        total = (
            material_total
            + Decimal("15") * usd_try
            + Decimal("80")
            + Decimal("20") * usd_try
            + Decimal("5") * usd_try
        ).quantize(Decimal("0.01"))

        ProductCost.objects.update_or_create(
            urun_kodu=card.urun.kod,
            defaults={
                "maliyet": total,
                "para_birimi": "TRY",
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0035_create_eylus_demo_material_cards"),
    ]

    operations = [
        migrations.RunPython(configure_demo_product_cards, migrations.RunPython.noop),
    ]
