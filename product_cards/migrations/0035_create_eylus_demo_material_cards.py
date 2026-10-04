import os
from decimal import Decimal
from django.db import migrations


def create_demo_material_cards(apps, schema_editor):
    if os.getenv("DEMO_MODE") != "1":
        return

    UrunKod = apps.get_model("core", "UrunKod")
    Material = apps.get_model("product_cards", "Material")

    specs = [
        ("UST_DANTEL", "üst dantel", "DANTEL", "SUSLEME", "M", "USD", Decimal("35.00"), Decimal("1.25")),
        ("BEDEN_TULU", "beden tülü", "TUL", "KESIM", "M", "USD", Decimal("2.00"), Decimal("0.10")),
        ("LEZ_DANTEL", "lez dantel", "DANTEL", "KESIM", "M", "USD", Decimal("18.00"), Decimal("0.75")),
        ("NAKIS_BONCUK", "nakış ve boncuk", "TAS", "SUSLEME", "ADET", "TRY", Decimal("1000.00"), Decimal("75.00")),
        ("ASTAR", "astar", "ASTAR", "KESIM", "M", "USD", Decimal("4.00"), Decimal("0.20")),
        ("TUL", "tül", "TUL", "KESIM", "M", "USD", Decimal("0.50"), Decimal("0.05")),
        ("SARF", "sarf malzemesi", "DIGER", "KESIM", "ADET", "TRY", Decimal("300.00"), Decimal("25.00")),
    ]

    products = UrunKod.objects.filter(kod__startswith="DM-").order_by("kod")
    for idx, product in enumerate(products):
        for j, (suffix, label, category, stage, unit, currency, base, step) in enumerate(specs):
            offset_index = ((idx * 3 + j * 2) % 7) - 3
            price = base + (step * Decimal(offset_index))
            if price <= 0:
                price = base

            Material.objects.update_or_create(
                kod=f"{product.kod}-{suffix}",
                defaults={
                    "ad": f"{product.kod} {label}",
                    "kategori": category,
                    "kullanim_asamasi": stage,
                    "birim": unit,
                    "stok_miktari": Decimal("0"),
                    "kritik_stok": Decimal("0"),
                    "tedarikci": "Demo Tedarikçi",
                    "aciklama": "EYLUS demo malzeme kartı",
                    "birim_maliyet": price,
                    "birim_maliyet_para_birimi": currency,
                    "aktif": True,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0034_merge_gbp_and_shipment_finance"),
        ("core", "0078_seed_demo_data"),
    ]

    operations = [
        migrations.RunPython(create_demo_material_cards, migrations.RunPython.noop),
    ]
