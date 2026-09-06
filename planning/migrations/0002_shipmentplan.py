from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_order_is_active"),
        ("planning", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="planningentry",
            name="section",
            field=models.CharField(
                choices=[
                    ("kesim", "Kesim Planlaması"),
                    ("dikim", "Dikim Planlaması"),
                    ("susleme", "Süsleme Planlaması"),
                    ("sevkiyat", "Sevkiyat Planlaması"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ShipmentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("planned_date", models.DateField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_shipment_plans", to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="shipment_plan", to="core.order")),
            ],
            options={"ordering": ["planned_date", "order__siparis_numarasi"]},
        ),
    ]
