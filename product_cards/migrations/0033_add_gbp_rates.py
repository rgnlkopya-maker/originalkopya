from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0032_sync_podyum_maras_prices"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangerate",
            name="gbp_try",
            field=models.DecimalField(decimal_places=6, default=1, max_digits=12),
        ),
        migrations.AddField(
            model_name="pricelistsettings",
            name="gbp_try",
            field=models.DecimalField(decimal_places=6, default=1, max_digits=12),
        ),
        migrations.AddField(
            model_name="showroomdraft",
            name="gbp_try",
            field=models.DecimalField(decimal_places=6, default=1, max_digits=12),
        ),
    ]
