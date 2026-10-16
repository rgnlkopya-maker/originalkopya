from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('product_cards', '0040_bizimhesapcustomer_address')]

    operations = [
        migrations.RemoveField(
            model_name='bizimhesapcustomermapping',
            name='invoice_address',
        ),
    ]
