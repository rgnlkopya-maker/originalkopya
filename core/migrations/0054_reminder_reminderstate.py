from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_add_modelleme_team"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField(blank=True, default="")),
                ("due_at", models.DateTimeField(db_index=True)),
                ("target_type", models.CharField(choices=[("all", "Herkes"), ("team", "Ekip / Görev"), ("user", "Belirli Personel")], db_index=True, default="all", max_length=10)),
                ("target_gorev", models.CharField(blank=True, default="", max_length=30)),
                ("repeat", models.CharField(choices=[("none", "Tek Sefer"), ("daily", "Her Gün"), ("weekly", "Her Hafta"), ("monthly", "Her Ay")], default="none", max_length=10)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_reminders", to=settings.AUTH_USER_MODEL)),
                ("target_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="targeted_reminders", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-due_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ReminderState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_completed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reminder", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="states", to="core.reminder")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminder_states", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="reminderstate",
            constraint=models.UniqueConstraint(fields=("reminder", "user"), name="unique_reminder_state_user"),
        ),
    ]
