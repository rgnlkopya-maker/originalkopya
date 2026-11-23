from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0057_standalone_proforma")]
    operations = [
        migrations.AddField(
            model_name="showroomdraft", name="delivery_date",
            field=models.DateField(null=True, blank=True),
        ),
    ]
