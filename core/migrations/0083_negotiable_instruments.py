from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0082_order_video"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="NegotiableInstrument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("CHECK","Çek"),("NOTE","Senet")], max_length=8)),
                ("direction", models.CharField(choices=[("IN","Alınan"),("OUT","Verilen")], max_length=3)),
                ("issuer_name", models.CharField(help_text="Çek sahibi/keşideci veya senet borçlusu", max_length=250)),
                ("received_from", models.CharField(blank=True, default="", max_length=250)),
                ("given_to", models.CharField(blank=True, default="", max_length=250)),
                ("bank", models.CharField(blank=True, default="", max_length=200)),
                ("branch", models.CharField(blank=True, default="", max_length=120)),
                ("document_number", models.CharField(blank=True, default="", max_length=120)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("currency", models.CharField(choices=[("TRY","TL"),("USD","USD"),("EUR","EUR"),("GBP","GBP")], default="TRY", max_length=3)),
                ("issue_date", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField()),
                ("status", models.CharField(choices=[("PORTFOLIO","Portföyde"),("ISSUED","Ödeme bekliyor"),("ENDORSED","Ciro edildi"),("BANK","Bankada"),("COLLECTED","Tahsil edildi"),("PAID","Ödendi"),("RETURNED","İade"),("BOUNCED","Karşılıksız"),("CANCELLED","İptal")], default="PORTFOLIO", max_length=16)),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(blank=True, help_text="Cari hesabına işlenecek MoliApp müşterisi", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="instruments", to="core.musteri")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["due_date","-id"]},
        ),
        migrations.CreateModel(
            name="InstrumentEndorser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=250)),
                ("note", models.CharField(blank=True, default="", max_length=300)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="endorsers", to="core.negotiableinstrument")),
            ],
            options={"ordering":["sequence","id"]},
        ),
        migrations.AddConstraint(model_name="instrumentendorser", constraint=models.UniqueConstraint(fields=("instrument","sequence"), name="unique_instrument_endorser_sequence")),
        migrations.CreateModel(
            name="InstrumentMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=40)),
                ("description", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="core.negotiableinstrument")),
            ],
            options={"ordering":["-created_at","-id"]},
        ),
    ]
