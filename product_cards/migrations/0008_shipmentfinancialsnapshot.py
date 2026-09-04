from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("product_cards", "0007_orderfinancialsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShipmentFinancialSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("usd_try", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("satis_fiyati", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("satis_para_birimi", models.CharField(default="TRY", max_length=3)),
                ("satis_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("urun_maliyeti_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("sevkiyat_ekstra_maliyet_tl", models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ("toplam_maliyet_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("gerceklesen_kar_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("gerceklesen_kar_orani", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("notlar", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shipment_financial_snapshot",
                        to="core.order",
                    ),
                ),
            ],
        ),
    ]
