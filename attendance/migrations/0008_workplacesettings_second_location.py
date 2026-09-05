from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0007_delete_legacy_mehmet_and_patron"),
    ]

    operations = [
        migrations.AddField(
            model_name="workplacesettings",
            name="second_location_name",
            field=models.CharField(blank=True, default="Gaziemir", max_length=120),
        ),
        migrations.AddField(
            model_name="workplacesettings",
            name="second_latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="workplacesettings",
            name="second_longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
    ]
