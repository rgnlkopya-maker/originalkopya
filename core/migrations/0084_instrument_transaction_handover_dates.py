from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0083_negotiable_instruments")]
    operations = [
        migrations.AddField(model_name="negotiableinstrument", name="transaction_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="negotiableinstrument", name="given_date", field=models.DateField(blank=True, null=True)),
    ]
