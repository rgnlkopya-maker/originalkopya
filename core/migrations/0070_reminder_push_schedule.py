from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0069_modazehra_hip_base_98"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="notify_interval_minutes",
            field=models.PositiveSmallIntegerField(default=15),
        ),
        migrations.AddField(
            model_name="reminderstate",
            name="last_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
