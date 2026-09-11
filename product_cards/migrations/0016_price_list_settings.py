from django.db import migrations, models
from django.utils import timezone


def seed_price_settings(apps, schema_editor):
    ExchangeRate = apps.get_model("product_cards", "ExchangeRate")
    PriceListSettings = apps.get_model("product_cards", "PriceListSettings")
    latest = ExchangeRate.objects.order_by("-rate_date", "-fetched_at").first()
    defaults = {
        "usd_try": latest.usd_try if latest else 1,
        "eur_try": getattr(latest, "eur_try", 1) if latest else 1,
        "rate_source": "TCMB",
        "rate_source_date": latest.source_date if latest else "",
        "rate_checked_at": latest.fetched_at if latest else None,
    }
    PriceListSettings.objects.get_or_create(pk=1, defaults=defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0015_normalize_tcmb_source_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangerate",
            name="eur_try",
            field=models.DecimalField(decimal_places=6, default=1, max_digits=12),
        ),
        migrations.CreateModel(
            name="PriceListSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("profit_rate", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("discount_rate", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("monthly_term_rate", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("usd_try", models.DecimalField(decimal_places=6, default=1, max_digits=12)),
                ("eur_try", models.DecimalField(decimal_places=6, default=1, max_digits=12)),
                ("rate_source", models.CharField(default="TCMB", max_length=30)),
                ("rate_source_date", models.CharField(blank=True, default="", max_length=20)),
                ("rate_checked_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(seed_price_settings, migrations.RunPython.noop),
    ]
