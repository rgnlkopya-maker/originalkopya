from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0057_standalone_proforma")]
    operations = [migrations.CreateModel(name="CompanyInvoiceProfile", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("company_name", models.CharField(max_length=250, blank=True, default="")),
        ("address", models.TextField(blank=True, default="")),
        ("tax_office", models.CharField(max_length=120, blank=True, default="")),
        ("tax_number", models.CharField(max_length=30, blank=True, default="")),
        ("mersis_number", models.CharField(max_length=40, blank=True, default="")),
        ("registry_number", models.CharField(max_length=50, blank=True, default="")),
        ("phone", models.CharField(max_length=50, blank=True, default="")),
        ("email", models.EmailField(blank=True, default="")),
        ("iban", models.CharField(max_length=60, blank=True, default="")),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ])]
