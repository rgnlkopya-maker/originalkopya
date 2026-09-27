from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0072_order_maliyet_indirimi"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionStageControlExclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("control_type", models.CharField(choices=[("stage_problem", "Üretim aşama problemi"), ("unshipped_7d", "7 gündür sevk edilmeyen")], max_length=30)),
                ("excluded_at", models.DateTimeField(auto_now_add=True)),
                ("excluded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="production_stage_exclusions", to="auth.user")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stage_control_exclusions", to="core.order")),
            ],
            options={"ordering": ["-excluded_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="productionstagecontrolexclusion",
            constraint=models.UniqueConstraint(fields=("order", "control_type"), name="unique_stage_control_exclusion"),
        ),
    ]
