import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0017_merge_salary_migrations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SalaryPaymentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveSmallIntegerField()),
                ("month", models.PositiveSmallIntegerField()),
                ("planned_on", models.DateField()),
                ("amount", models.DecimalField(max_digits=13, decimal_places=2)),
                ("kind", models.CharField(max_length=12, choices=[("advance", "Avans"), ("payment", "Maaş Ödemesi")], default="advance")),
                ("note", models.CharField(max_length=300, blank=True, default="")),
                ("completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_salary_payment_plans", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="salary_payment_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["planned_on", "id"]},
        ),
    ]
