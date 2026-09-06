from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0007_delete_legacy_mehmet_and_patron"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeehrprofile",
            name="chronic_conditions",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="employeehrprofile",
            name="medications",
            field=models.TextField(blank=True, default=""),
        ),
    ]
