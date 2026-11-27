from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0073_shipment_exchange_rates")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="invoice_shipment_release_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
