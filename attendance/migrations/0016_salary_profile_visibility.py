from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0015_salary_management")]

    operations = [
        migrations.AddField(
            model_name="salaryprofile",
            name="visible_in_salary",
            field=models.BooleanField(default=True),
        ),
    ]
