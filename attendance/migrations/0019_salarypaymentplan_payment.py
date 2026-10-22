import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0018_salarypaymentplan")]
    operations = [
        migrations.AddField(
            model_name="salarypaymentplan", name="payment",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment_plan", to="attendance.salarytransaction"),
        ),
    ]
