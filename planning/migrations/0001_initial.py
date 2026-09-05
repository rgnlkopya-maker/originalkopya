from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="PlanningEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("section", models.CharField(choices=[("kesim", "Kesim Planlaması"), ("dikim", "Dikim Planlaması"), ("susleme", "Süsleme Planlaması")], max_length=20)),
                ("date", models.DateField()),
                ("note", models.TextField(blank=True, default="")),
                ("text_color", models.CharField(default="#182033", max_length=7)),
                ("background_color", models.CharField(default="#ffffff", max_length=7)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["date", "section"]},
        ),
        migrations.AddConstraint(
            model_name="planningentry",
            constraint=models.UniqueConstraint(fields=("section", "date"), name="unique_planning_section_date"),
        ),
    ]
