from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0058_company_invoice_profile")]
    operations = [migrations.AddField(model_name="standaloneinvoiceline", name="order", field=models.OneToOneField(to="core.order", null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="standalone_invoice_line"))]
