from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('product_cards', '0039_invoice_due_date')]

    operations = [
        migrations.AddField(
            model_name='bizimhesapcustomermapping',
            name='invoice_address',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
