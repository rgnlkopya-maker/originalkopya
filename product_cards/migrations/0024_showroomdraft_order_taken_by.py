from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0023_showroomdraft_vat_rate")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="order_taken_by",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
