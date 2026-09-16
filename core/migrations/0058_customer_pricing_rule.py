from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def create_modazehra_rule(apps, schema_editor):
    Musteri = apps.get_model("core", "Musteri")
    CustomerPricingRule = apps.get_model("core", "CustomerPricingRule")
    for customer in Musteri.objects.filter(ad__iexact="MODAZEHRADA"):
        CustomerPricingRule.objects.get_or_create(
            customer=customer,
            defaults={
                "active": True,
                "base_size": 38,
                "base_hip_max": Decimal("102"),
                "hip_step": Decimal("4"),
                "size_step": 2,
                "price_group_size": 3,
                "price_step": Decimal("250"),
            },
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0057_customerdetail")]

    operations = [
        migrations.CreateModel(
            name="CustomerPricingRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active", models.BooleanField(default=True)),
                ("base_size", models.PositiveSmallIntegerField(default=38)),
                ("base_hip_max", models.DecimalField(decimal_places=2, default=Decimal("102"), max_digits=6)),
                ("hip_step", models.DecimalField(decimal_places=2, default=Decimal("4"), max_digits=6)),
                ("size_step", models.PositiveSmallIntegerField(default=2)),
                ("price_group_size", models.PositiveSmallIntegerField(default=3)),
                ("price_step", models.DecimalField(decimal_places=2, default=Decimal("250"), max_digits=12)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="pricing_rule", to="core.musteri")),
            ],
        ),
        migrations.AddField(
            model_name="order",
            name="customer_base_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_price_adjustment",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_pricing_rule",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="order",
            name="hip_measurement",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.RunPython(create_modazehra_rule, migrations.RunPython.noop),
    ]
