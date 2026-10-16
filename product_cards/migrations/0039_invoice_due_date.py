from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('product_cards', '0038_bizimhesap_invoice_transfer')]
    operations = [migrations.AddField(model_name='invoicedraft', name='due_date', field=models.DateField(null=True, blank=True))]
