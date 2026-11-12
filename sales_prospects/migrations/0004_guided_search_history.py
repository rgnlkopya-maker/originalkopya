from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sales_prospects", "0003_business_contact_channels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GuidedSearch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("country", models.CharField(max_length=8, choices=[
                    ("DE", "Almanya"), ("FR", "Fransa"), ("GB", "Birleşik Krallık"),
                    ("US", "ABD"), ("NL", "Hollanda"), ("BE", "Belçika"),
                    ("AT", "Avusturya"), ("CH", "İsviçre"), ("ES", "İspanya"),
                    ("IT", "İtalya"), ("AE", "Birleşik Arap Emirlikleri"),
                    ("SA", "Suudi Arabistan"), ("OTHER", "Diğer"),
                ])),
                ("city", models.CharField(blank=True, default="", max_length=100)),
                ("query", models.CharField(max_length=300)),
                ("google_url", models.URLField(max_length=1100)),
                ("captured_count", models.PositiveIntegerField(default=0)),
                ("added_count", models.PositiveIntegerField(default=0)),
                ("duplicate_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("last_import_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="export_guided_searches", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="GuidedSearchHit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_url", models.URLField(max_length=500)),
                ("original_title", models.CharField(blank=True, default="", max_length=180)),
                ("was_new", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("prospect", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="guided_hits", to="sales_prospects.prospect",
                )),
                ("search", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="hits", to="sales_prospects.guidedsearch",
                )),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddConstraint(
            model_name="guidedsearchhit",
            constraint=models.UniqueConstraint(
                fields=("search", "prospect"), name="unique_guided_search_prospect"
            ),
        ),
    ]
