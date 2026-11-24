from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PreparationStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("color", models.CharField(max_length=100)),
                ("size", models.CharField(blank=True, default="", max_length=20)),
                ("stage", models.CharField(max_length=40, choices=[["danteli_ayarlandi","Danteli Ayarlandı"],["etek_danteli_ayarlandi","Etek Danteli Ayarlandı"],["beden_danteli_ayarlandi","Beden Danteli Ayarlandı"],["takim_olarak_danteli_ayarlandi","Takım Olarak Danteli Ayarlandı"]])),
                ("initial_quantity", models.PositiveIntegerField()),
                ("remaining", models.PositiveIntegerField()),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("prepared_by", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.urunkod")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="product_cards.warehouse")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="PreparationUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.orderevent")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.order")),
                ("stock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uses", to="inventory.preparationstock")),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
