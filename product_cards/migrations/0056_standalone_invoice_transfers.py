from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0055_standalone_invoice")]
    operations = [
        migrations.CreateModel(
            name="StandaloneInvoiceTransfer",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("platform", models.CharField(max_length=16, choices=[("bizimhesap", "BizimHesap"), ("parasut", "Paraşüt")])),
                ("status", models.CharField(max_length=16, default="NOT_SENT")),
                ("external_invoice_id", models.CharField(max_length=100, blank=True, default="")),
                ("last_error", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transfers", to="product_cards.standaloneinvoice")),
            ],
        ),
        migrations.AddConstraint(model_name="standaloneinvoicetransfer", constraint=models.UniqueConstraint(fields=("invoice", "platform"), name="unique_standalone_invoice_platform")),
    ]
