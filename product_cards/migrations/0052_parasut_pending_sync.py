from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0051_invoice_open_account_list_label")]
    operations = [migrations.AddField(model_name="parasutinvoicetransfer", name="needs_sync", field=models.BooleanField(default=False))]
