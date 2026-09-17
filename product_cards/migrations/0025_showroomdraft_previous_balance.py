from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0024_showroomdraft_order_taken_by")]

    operations = [
        migrations.AddField(
            model_name="showroomdraft",
            name="previous_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=16),
        ),
    ]
