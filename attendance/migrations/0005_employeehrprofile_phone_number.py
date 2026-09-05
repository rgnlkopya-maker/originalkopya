from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0004_employeehrprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeehrprofile",
            name="phone_number",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
    ]
