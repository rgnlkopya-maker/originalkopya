from decimal import Decimal
from django.db import migrations

# Approved 15 October 2026: exactly these 78 active, unshipped, zero-VAT orders.
ORDER_IDS = [151,152,156,426,427,428,429,430,431,432,433,434,435,436,437,438,439,440,441,442,443,444,445,446,447,448,449,450,451,452,453,454,455,456,457,458,459,460,461,462,463,380,145,146,149,162,183,184,185,327,334,337,219,220,221,222,223,224,226,227,228,230,231,232,233,234,124,125,126,128,129,212,410,411,403,408,422,423]
APPROVED_CUSTOMERS = [
    "ELENORA ANTEP",
    "MODA ZEHRADA",
    "MOTİF DENİZLİ",
    "LARA ŞAHİN TAHİNCİOĞLU İSTANBUL",
    "DIAMOND ANKARA SEHER KUTLU",
    "KUTLU CENTER ANKARA SERDAR KUTLU",
    "YENİ ARAS",
    "GÜLAY GİYİM",
    "SİTARE SARAÇLAR",
    "TUĞRA ANKARA EMRAH KUTLU"
]


def apply_approved_vat(apps, schema_editor):
    Order = apps.get_model("core", "Order")
    InvoiceLine = apps.get_model("product_cards", "InvoiceLine")
    db = schema_editor.connection.alias
    qs = (Order.objects.using(db).filter(
        pk__in=ORDER_IDS, is_active=True, vat_rate=Decimal("0"),
        musteri__ad__in=APPROVED_CUSTOMERS,
    ).exclude(sevkiyat_durum="gonderildi"))
    # No invoice draft / issued invoice is allowed to become inconsistent.
    linked = InvoiceLine.objects.using(db).filter(order_id__in=ORDER_IDS).exists()
    if linked:
        raise RuntimeError("VAT migration stopped: invoice link detected; no orders changed.")
    if qs.count() != len(ORDER_IDS):
        raise RuntimeError("VAT migration stopped: 78 approved orders no longer match; no orders changed.")
    changed = qs.update(vat_rate=Decimal("10.00"))
    if changed != len(ORDER_IDS):
        raise RuntimeError("VAT migration stopped: update count differs from 78.")


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0035_invoice_drafts"),
        ("core", "0077_alter_productionstagecontrolexclusion_control_type"),
    ]
    operations = [migrations.RunPython(apply_approved_vat, migrations.RunPython.noop)]
