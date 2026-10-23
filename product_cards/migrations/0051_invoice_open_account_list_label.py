from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0050_restore_verified_official_invoice_numbers")]
    operations = [migrations.AddField(model_name="invoicedraft", name="show_open_account_in_list", field=models.BooleanField(default=False))]
