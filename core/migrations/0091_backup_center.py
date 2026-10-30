from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0090_expand_instrument_kind_choices")]
    operations = [
        migrations.CreateModel(
            name="BackupPolicy",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("module", models.CharField(max_length=20, unique=True, choices=[("folios","Sipariş Föyleri"),("instruments","Çek / Senet")])),
                ("frequency", models.CharField(max_length=10, default="off", choices=[("daily","Her gün"),("weekly","Haftalık"),("off","Kapalı")])),
                ("hour", models.PositiveSmallIntegerField(default=3)),
                ("minute", models.PositiveSmallIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="BackupExecution",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("module", models.CharField(max_length=20, choices=[("folios","Sipariş Föyleri"),("instruments","Çek / Senet")])),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("success", models.BooleanField(default=False)),
                ("files", models.PositiveIntegerField(default=0)),
                ("photos", models.PositiveIntegerField(default=0)),
                ("records", models.PositiveIntegerField(default=0)),
                ("message", models.CharField(max_length=255, blank=True)),
            ],
            options={"ordering":["-started_at"]},
        ),
    ]
