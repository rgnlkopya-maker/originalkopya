from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0054_sync_existing_draft_invoice_currency"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="StandaloneInvoice", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("invoice_date", models.DateField()), ("due_date", models.DateField(blank=True, null=True)),
            ("currency", models.CharField(default="TRY", max_length=3)),
            ("note", models.TextField(blank=True, default="")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.musteri")),
        ]),
        migrations.CreateModel(name="StandaloneInvoiceLine", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("description", models.CharField(max_length=300)),
            ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=12)),
            ("unit", models.CharField(default="Adet", max_length=20)),
            ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
            ("vat_rate", models.DecimalField(decimal_places=2, default=10, max_digits=7)),
            ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="product_cards.standaloneinvoice")),
        ]),
    ]
