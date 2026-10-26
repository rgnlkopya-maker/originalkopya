from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0056_standalone_invoice_transfers")]
    operations = [migrations.AddField(model_name="standaloneinvoice", name="is_proforma", field=models.BooleanField(default=False))]
