from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product_cards', '0041_remove_bizimhesap_mapping_address')]

    operations = [
        migrations.AddField(model_name='invoicedraft', name='bizimhesap_manual_recorded', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='invoicedraft', name='parasut_manual_recorded', field=models.BooleanField(default=False)),
    ]
