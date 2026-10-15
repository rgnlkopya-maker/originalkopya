from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0034_merge_gbp_and_shipment_finance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="InvoiceDraft", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("invoice_date", models.DateField()),
            ("status", models.CharField(choices=[("DRAFT", "Taslak"), ("FINAL", "Faturalandırıldı")], default="DRAFT", max_length=8)),
            ("currency", models.CharField(default="TRY", max_length=3)),
            ("official_number", models.CharField(blank=True, default="", max_length=80)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_drafts", to="core.musteri")),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-invoice_date", "-id"]}),
        migrations.CreateModel(name="InvoiceLine", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("price", models.DecimalField(decimal_places=2, max_digits=14)),
            ("vat_rate", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="product_cards.invoicedraft")),
            ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_line", to="core.order")),
        ]),
        migrations.AddConstraint(model_name="invoicedraft", constraint=models.UniqueConstraint(fields=("customer", "invoice_date", "currency"), condition=models.Q(status="DRAFT"), name="one_open_invoice_per_customer_day_currency")),
    ]
