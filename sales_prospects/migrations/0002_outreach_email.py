from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sales_prospects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="prospect", name="email",
            field=models.EmailField(blank=True, default="", max_length=254)),
        migrations.AddField(model_name="prospect", name="contact_class",
            field=models.CharField(choices=[("UNKNOWN", "Belirsiz"), ("COMPANY", "Tüzel kişi / şirket"), ("PERSON", "Şahıs işletmesi")], default="UNKNOWN", max_length=8)),
        migrations.AddField(model_name="prospect", name="email_basis",
            field=models.CharField(choices=[("NONE", "İncelenmedi"), ("CONSENT", "Açık iletişim izni"), ("US_B2B", "ABD B2B değerlendirmesi"), ("GB_CORP", "Birleşik Krallık kurumsal B2B değerlendirmesi"), ("NO", "İletişim kurulmayacak")], default="NONE", max_length=8)),
        migrations.AddField(model_name="prospect", name="email_source_note",
            field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="prospect", name="email_checked",
            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="prospect", name="outreach_approved_at",
            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="prospect", name="outreach_approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_export_prospects", to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(
            name="SuppressedEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("reason", models.CharField(default="UNSUBSCRIBE", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="OutreachEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("INITIAL", "İlk tanıtım"), ("FOLLOWUP", "Tek takip")], default="INITIAL", max_length=8)),
                ("email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=180)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("QUEUED", "Kuyrukta"), ("SENDING", "Gönderiliyor"), ("SENT", "Gönderildi"), ("FAILED", "Hata"), ("CANCELLED", "İptal")], db_index=True, default="QUEUED", max_length=12)),
                ("scheduled_at", models.DateTimeField(db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("error_message", models.CharField(blank=True, default="", max_length=300)),
                ("approved_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("prospect", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outreach_emails", to="sales_prospects.prospect")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="outreachemail",
            constraint=models.UniqueConstraint(fields=("prospect", "kind"), name="unique_export_message_kind"),
        ),
    ]
