from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0059_match_modazehra_customer_name")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="vat_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=7,
                verbose_name="KDV Oranı (%)",
            ),
        ),
    ]
