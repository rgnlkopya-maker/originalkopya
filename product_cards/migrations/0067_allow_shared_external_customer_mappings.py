from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0066_showroom_folio_photos"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="bizimhesapcustomermapping",
            name="unique_bizimhesap_customer_id",
        ),
        migrations.AlterField(
            model_name="parasutcustomermapping",
            name="external_contact_id",
            field=models.CharField(max_length=100),
        ),
    ]
