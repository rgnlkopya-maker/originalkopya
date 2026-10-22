import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("attendance", "0015_salary_management"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="SalaryRate",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("monthly_net",models.DecimalField(decimal_places=2,max_digits=13)),
            ("start_date",models.DateField()),
            ("end_date",models.DateField(blank=True,null=True)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("user",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="salary_rates",to=settings.AUTH_USER_MODEL)),
            ("created_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="created_salary_rates",to=settings.AUTH_USER_MODEL)),
        ],options={"ordering":["-start_date","-id"],"constraints":[models.UniqueConstraint(fields=("user","start_date"),name="unique_salary_rate_start")]}),
    ]
