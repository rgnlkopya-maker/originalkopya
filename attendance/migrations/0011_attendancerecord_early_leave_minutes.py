from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0010_attendancedevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="early_leave_minutes",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
