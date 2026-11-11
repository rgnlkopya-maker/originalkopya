from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0094_notificationpreference"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="destination_url",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.CreateModel(
            name="CustomerMonitorState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("last_checked_on", models.DateField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
