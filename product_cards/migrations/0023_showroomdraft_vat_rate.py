from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0022_showroomdraft_orders_created")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="vat_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
    ]
