from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0088_instrument_backup_run")]
    operations = [
        migrations.CreateModel(
            name="InstrumentDriveHealth",
            fields=[
                ("key", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(default="unchecked", max_length=16)),
                ("message", models.CharField(blank=True, default="", max_length=250)),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
