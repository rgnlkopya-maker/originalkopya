from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0062_shared_invoice_number")]
    operations = [
        migrations.AddField(model_name="standaloneinvoice", name="official_number", field=models.CharField(max_length=80, blank=True, default="")),
        migrations.AddField(model_name="standaloneinvoice", name="show_open_account_in_list", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="standaloneinvoice", name="bizimhesap_display_status", field=models.CharField(max_length=8, blank=True, default="")),
        migrations.AddField(model_name="standaloneinvoice", name="parasut_display_status", field=models.CharField(max_length=8, blank=True, default="")),
    ]
