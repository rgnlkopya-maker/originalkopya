from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="SearchRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_date", models.DateField(unique=True)),
                ("status", models.CharField(choices=[("RUNNING", "Çalışıyor"), ("DONE", "Tamamlandı"), ("ERROR", "Hata")], default="RUNNING", max_length=8)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("searched_countries", models.CharField(blank=True, default="", max_length=120)),
                ("error_message", models.CharField(blank=True, default="", max_length=300)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ("-run_date",)},
        ),
        migrations.CreateModel(
            name="Prospect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("country", models.CharField(choices=[("DE", "Almanya"), ("FR", "Fransa"), ("GB", "Birleşik Krallık"), ("US", "ABD"), ("NL", "Hollanda"), ("BE", "Belçika"), ("AT", "Avusturya"), ("CH", "İsviçre"), ("ES", "İspanya"), ("IT", "İtalya"), ("AE", "Birleşik Arap Emirlikleri"), ("SA", "Suudi Arabistan"), ("OTHER", "Diğer")], db_index=True, max_length=8)),
                ("city", models.CharField(blank=True, default="", max_length=100)),
                ("website_url", models.URLField(blank=True, max_length=500)),
                ("instagram_url", models.URLField(blank=True, max_length=500)),
                ("source_url", models.URLField(blank=True, max_length=500)),
                ("canonical_url", models.CharField(max_length=500, unique=True)),
                ("source_snippet", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("NEW", "İncelenecek"), ("REVIEWED", "İncelendi"), ("APPROVED", "İletişime uygun"), ("CONTACTED", "Mesaj gönderildi"), ("REPLIED", "Yanıt geldi"), ("QUALIFIED", "Potansiyel toptancı"), ("CUSTOMER", "Müşteri oldu"), ("REJECTED", "Uygun değil")], db_index=True, default="NEW", max_length=12)),
                ("note", models.TextField(blank=True, default="")),
                ("message_draft", models.TextField(blank=True, default="")),
                ("source", models.CharField(choices=[("WEB", "Web araması"), ("MANUAL", "Elle eklendi")], default="MANUAL", max_length=8)),
                ("last_contacted_at", models.DateTimeField(blank=True, null=True)),
                ("next_followup_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
    ]
