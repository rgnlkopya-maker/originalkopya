from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0089_instrument_drive_health")]
    operations = [
        migrations.AlterField(
            model_name="negotiableinstrument",
            name="kind",
            field=models.CharField(
                max_length=8,
                choices=[
                    ("CHECK", "Çek"),
                    ("NOTE", "Senet"),
                    ("CK_CUST", "Müşteri Çeki"),
                    ("CK_END", "Cirolu Müşteri Çeki"),
                    ("CK_OWN", "Kendi Çekimiz"),
                    ("NT_CUST", "Müşteri Senedi"),
                    ("NT_END", "Cirolu Müşteri Senedi"),
                    ("NT_OWN", "Kendi Senedimiz"),
                ],
            ),
        ),
    ]
