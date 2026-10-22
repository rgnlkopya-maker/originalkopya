import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0014_attendancerecord_checkout_forgotten"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name="SalaryProfile", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("monthly_net", models.DecimalField(decimal_places=2, default=0, max_digits=13)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="salary_profile", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="SalaryPeriod", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("year", models.PositiveSmallIntegerField()),
            ("month", models.PositiveSmallIntegerField()),
            ("base_net", models.DecimalField(decimal_places=2, max_digits=13)),
            ("adjustment", models.DecimalField(decimal_places=2, default=0, max_digits=13)),
            ("deduction", models.DecimalField(decimal_places=2, default=0, max_digits=13)),
            ("locked", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="salary_periods", to=settings.AUTH_USER_MODEL)),
        ], options={"constraints": [models.UniqueConstraint(fields=("user", "year", "month"), name="unique_salary_period")]}),
        migrations.CreateModel(name="SalaryTransaction", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("amount", models.DecimalField(decimal_places=2, max_digits=13)),
            ("paid_on", models.DateField()),
            ("method", models.CharField(choices=[("cash", "Nakit"), ("bank", "Banka"), ("other", "Diğer")], default="cash", max_length=12)),
            ("kind", models.CharField(choices=[("payment", "Maaş Ödemesi"), ("advance", "Avans")], default="payment", max_length=12)),
            ("note", models.CharField(blank=True, default="", max_length=300)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("voided_at", models.DateTimeField(blank=True, null=True)),
            ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="attendance.salaryperiod")),
            ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="salary_payments_recorded", to=settings.AUTH_USER_MODEL)),
            ("voided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="salary_payments_voided", to=settings.AUTH_USER_MODEL)),
        ]),
    ]
