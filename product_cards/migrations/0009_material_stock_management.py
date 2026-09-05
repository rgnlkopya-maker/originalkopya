from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_opening_movements(apps, schema_editor):
    Material = apps.get_model("product_cards", "Material")
    Movement = apps.get_model("product_cards", "MaterialStockMovement")
    for material in Material.objects.all():
        stock = material.stok_miktari or Decimal("0")
        if stock != 0:
            Movement.objects.create(
                material=material,
                movement_type="BASLANGIC",
                miktar=stock,
                onceki_stok=Decimal("0"),
                sonraki_stok=stock,
                aciklama="Mevcut stok kaydından açılış hareketi oluşturuldu.",
            )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0008_shipmentfinancialsnapshot"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="kategori",
            field=models.CharField(
                choices=[
                    ("KUMAS", "Kumaş"),
                    ("TUL", "Tül"),
                    ("DANTEL", "Dantel"),
                    ("ASTAR", "Astar"),
                    ("TAS", "Taş / Boncuk"),
                    ("FERMUAR", "Fermuar / Aksesuar"),
                    ("DIGER", "Diğer"),
                ],
                default="DIGER",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="kritik_stok",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="material",
            name="tedarikci",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="material",
            name="aciklama",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="material",
            name="son_alis_tarihi",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="MaterialStockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("GIRIS", "Stok Girişi"), ("CIKIS", "Stok Çıkışı"), ("IADE", "İade Girişi"), ("FIRE", "Fire / Zayi"), ("DUZELTME_ARTI", "Sayım Düzeltmesi +"), ("DUZELTME_EKSI", "Sayım Düzeltmesi -"), ("BASLANGIC", "Başlangıç Stoğu")], max_length=20)),
                ("miktar", models.DecimalField(decimal_places=3, max_digits=14)),
                ("onceki_stok", models.DecimalField(decimal_places=3, max_digits=14)),
                ("sonraki_stok", models.DecimalField(decimal_places=3, max_digits=14)),
                ("aciklama", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("islem_yapan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="material_stock_movements", to=settings.AUTH_USER_MODEL)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="product_cards.material")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.RunPython(create_opening_movements, migrations.RunPython.noop),
    ]
