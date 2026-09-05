from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0003_alter_attendancerecord_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeHRProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employment_start_date", models.DateField(blank=True, null=True)),
                ("sgk_start_date", models.DateField(blank=True, null=True)),
                ("birth_date", models.DateField(blank=True, null=True)),
                ("annual_leave_carryover", models.PositiveIntegerField(default=0)),
                ("note", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="hr_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
