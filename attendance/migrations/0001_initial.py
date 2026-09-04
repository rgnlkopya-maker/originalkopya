import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="WorkplaceSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Moli Tekstil", max_length=120)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("normal_radius_m", models.PositiveIntegerField(default=50)),
                ("overtime_radius_m", models.PositiveIntegerField(default=100)),
                ("work_start", models.TimeField(default="08:30")),
                ("work_end", models.TimeField(default="19:00")),
                ("late_tolerance_minutes", models.PositiveIntegerField(default=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="AttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("work_date", models.DateField(db_index=True)),
                ("check_in", models.DateTimeField(blank=True, null=True)),
                ("check_out", models.DateTimeField(blank=True, null=True)),
                ("check_in_latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("check_in_longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("check_out_latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("check_out_longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("check_in_distance_m", models.PositiveIntegerField(blank=True, null=True)),
                ("check_out_distance_m", models.PositiveIntegerField(blank=True, null=True)),
                ("late_minutes", models.PositiveIntegerField(default=0)),
                ("overtime_minutes", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-work_date", "user__username"]},
        ),
        migrations.AddConstraint(
            model_name="attendancerecord",
            constraint=models.UniqueConstraint(fields=("user", "work_date"), name="unique_user_attendance_day"),
        ),
        migrations.AddIndex(
            model_name="attendancerecord",
            index=models.Index(fields=["work_date", "user"], name="attendance__work_da_61b46c_idx"),
        ),
    ]
