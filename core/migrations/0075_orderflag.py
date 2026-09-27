from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0074_ordernoticeread"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.TextField()),
                ("mode", models.CharField(choices=[("TRACK_ALL", "Tüm üretim hareketlerini takip et"), ("STAGE_ALERT", "Seçili üretim aşamalarında uyar")], default="TRACK_ALL", max_length=20)),
                ("trigger_stages", models.JSONField(blank=True, default=list)),
                ("popup_actor", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_order_flags", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="flags", to="core.order")),
                ("notify_users", models.ManyToManyField(blank=True, related_name="followed_order_flags", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="orderflag",
            index=models.Index(fields=["order", "is_active"], name="core_orderf_order_i_2b5db2_idx"),
        ),
    ]
