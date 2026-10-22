from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0019_salarypaymentplan_payment")]
    operations = [
        migrations.AddField(
            model_name="salarypaymentplan",
            name="method",
            field=models.CharField(max_length=12, choices=[("cash", "Elden"), ("bank", "Bankadan")], default="cash"),
        ),
    ]
