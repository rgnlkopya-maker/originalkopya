from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0033_add_gbp_rates"),
        ("product_cards", "0033_sync_existing_shipment_finance"),
    ]

    operations = []
