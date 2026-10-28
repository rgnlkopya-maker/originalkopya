from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0087_instrument_backup_connection")]
    operations = [
        migrations.CreateModel(
            name="InstrumentBackupRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("success", models.BooleanField(default=False)),
                ("record_count", models.PositiveIntegerField(default=0)),
                ("new_photo_count", models.PositiveIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, default="", max_length=40)),
            ],
            options={"ordering": ["-started_at", "-id"]},
        )
    ]
