from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_alter_order_siparis_tipi"),
        ("product_cards", "0006_productcard_finance_embroidery_packaging"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderFinancialSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("usd_try", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("satis_fiyati", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("satis_para_birimi", models.CharField(default="TRY", max_length=3)),
                ("satis_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("maliyet_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("beklenen_kar_tl", models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ("beklenen_kar_orani", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_snapshot",
                        to="core.order",
                    ),
                ),
            ],
        ),
    ]
