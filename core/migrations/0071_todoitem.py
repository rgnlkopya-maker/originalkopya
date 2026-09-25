from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0070_reminder_push_schedule"),
    ]

    operations = [
        migrations.CreateModel(
            name="TodoItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("note", models.TextField(blank=True, default="")),
                ("due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("alarm_enabled", models.BooleanField(db_index=True, default=False)),
                ("alarm_interval_minutes", models.PositiveSmallIntegerField(default=15)),
                ("last_notified_at", models.DateTimeField(blank=True, null=True)),
                ("snoozed_until", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="todo_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["completed_at", "due_at", "-created_at"]},
        ),
    ]
