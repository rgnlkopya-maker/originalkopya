from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0080_merge_freeze_and_customer_billing")]
    operations = [
        migrations.AddField(model_name="order", name="detail_printed", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="order", name="main_image_printed", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="orderimage", name="printed", field=models.BooleanField(default=False)),
    ]
