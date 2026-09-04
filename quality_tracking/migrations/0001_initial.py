from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0052_finans_hareketlerini_son_durumdan_ayir"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QualityIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("konu", models.CharField(max_length=180)),
                ("aciklama", models.TextField()),
                ("asama", models.CharField(choices=[("GENEL", "Genel"), ("MALZEME", "Malzeme"), ("KESIM", "Kesim"), ("DIKIM", "Dikim"), ("NAKIS", "Nakış"), ("SUSLEME", "Süsleme"), ("HAZIR", "Hazır"), ("SEVKIYAT", "Sevkiyat")], default="GENEL", max_length=20)),
                ("durum", models.CharField(choices=[("ACIK", "Açık"), ("COZULDU", "Çözüldü")], db_index=True, default="ACIK", max_length=10)),
                ("cozum_notu", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("kaydeden", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_quality_issues", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quality_issues", to="core.order")),
                ("sorumlu_personeller", models.ManyToManyField(blank=True, related_name="quality_issues", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="qualityissue",
            index=models.Index(fields=["order", "durum"], name="quality_tra_order_i_552f25_idx"),
        ),
        migrations.AddIndex(
            model_name="qualityissue",
            index=models.Index(fields=["created_at"], name="quality_tra_created_62c25d_idx"),
        ),
    ]
