from decimal import Decimal

from django.db import migrations, models


def update_modazehra_hip_base(apps, schema_editor):
    Musteri = apps.get_model("core", "Musteri")
    CustomerPricingRule = apps.get_model("core", "CustomerPricingRule")

    for customer in Musteri.objects.all().iterator():
        normalized = "".join(ch for ch in (customer.ad or "").upper() if ch.isalnum())
        if normalized in {"MODAZEHRA", "MODAZEHRADA"}:
            CustomerPricingRule.objects.update_or_create(
                customer=customer,
                defaults={
                    "active": True,
                    "base_size": 38,
                    "base_hip_max": Decimal("98"),
                    "hip_step": Decimal("4"),
                    "size_step": 2,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0068_pushsubscription"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customerpricingrule",
            name="base_hip_max",
            field=models.DecimalField(decimal_places=2, default=Decimal("98"), max_digits=6),
        ),
        migrations.RunPython(update_modazehra_hip_base, migrations.RunPython.noop),
    ]
