from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0010_cut_stock_movements")]

    operations = [
        migrations.AddField(
            model_name="productmaterial",
            name="kullanim_asamasi",
            field=models.CharField(
                choices=[("KESIM", "Kesim Malzemesi"), ("SUSLEME", "Süsleme Malzemesi")],
                default="KESIM",
                max_length=12,
            ),
        ),
    ]
