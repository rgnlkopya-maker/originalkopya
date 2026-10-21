from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0002_shipmentplan"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SerialCutPlan",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("planned_date", models.DateField(db_index=True)),
                ("quantity", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="serial_cut_plans", to="core.order")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["planned_date", "id"], "constraints": [models.UniqueConstraint(fields=["order", "planned_date"], name="unique_serial_cut_order_day")]},
        ),
    ]
