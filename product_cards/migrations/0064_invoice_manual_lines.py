from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0063_manual_invoice_list_controls")]
    operations = [
        migrations.CreateModel(
            name="InvoiceManualLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=300)),
                ("quantity", models.DecimalField(decimal_places=3, default=1, max_digits=12)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("vat_rate", models.DecimalField(decimal_places=2, default=10, max_digits=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="manual_lines", to="product_cards.invoicedraft")),
            ],
        ),
    ]
