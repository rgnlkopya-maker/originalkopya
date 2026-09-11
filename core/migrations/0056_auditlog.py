from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0055_mark_existing_orders_seen"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username_snapshot", models.CharField(blank=True, max_length=150)),
                ("action", models.CharField(max_length=160)),
                ("method", models.CharField(max_length=10)),
                ("path", models.CharField(max_length=500)),
                ("object_ref", models.CharField(blank=True, max_length=200)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                ("status_code", models.PositiveSmallIntegerField(default=200)),
                ("success", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["user", "created_at"], name="core_audit_user_created_idx"),
                    models.Index(fields=["action", "created_at"], name="core_audit_action_created_idx"),
                ],
            },
        ),
    ]
