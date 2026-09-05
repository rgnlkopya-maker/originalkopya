from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0005_employeehrprofile_phone_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeehrprofile",
            name="national_id",
            field=models.CharField(blank=True, default="", max_length=11),
        ),
        migrations.AddField(
            model_name="employeehrprofile",
            name="emergency_contact_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="employeehrprofile",
            name="emergency_contact_phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="employeehrprofile",
            name="employment_end_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
