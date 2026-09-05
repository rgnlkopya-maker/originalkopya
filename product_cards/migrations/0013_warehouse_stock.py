from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


def seed_warehouses_and_stocks(apps, schema_editor):
    Warehouse = apps.get_model("product_cards", "Warehouse")
    Material = apps.get_model("product_cards", "Material")
    MaterialWarehouseStock = apps.get_model("product_cards", "MaterialWarehouseStock")
    MaterialStockMovement = apps.get_model("product_cards", "MaterialStockMovement")

    merkez, _ = Warehouse.objects.get_or_create(kod="MERKEZ", defaults={"ad": "Merkez", "aktif": True})
    Warehouse.objects.get_or_create(kod="GAZIEMIR", defaults={"ad": "Gaziemir", "aktif": True})

    for material in Material.objects.all():
        stock = material.stok_miktari or Decimal("0")
        ws, _ = MaterialWarehouseStock.objects.get_or_create(material=material, warehouse=merkez, defaults={"miktar": stock})
        if ws.miktar == 0 and stock > 0:
            ws.miktar = stock
            ws.save(update_fields=["miktar"])
        MaterialStockMovement.objects.filter(material=material, warehouse__isnull=True).update(warehouse=merkez)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0012_material_usage_stage")]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kod", models.CharField(max_length=20, unique=True)),
                ("ad", models.CharField(max_length=80)),
                ("aktif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["ad"]},
        ),
        migrations.CreateModel(
            name="MaterialWarehouseStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("miktar", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="warehouse_stocks", to="product_cards.material")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="material_stocks", to="product_cards.warehouse")),
            ],
            options={"ordering": ["material__ad", "warehouse__ad"]},
        ),
        migrations.AddConstraint(
            model_name="materialwarehousestock",
            constraint=models.UniqueConstraint(fields=("material", "warehouse"), name="unique_material_warehouse_stock"),
        ),
        migrations.AddField(
            model_name="materialstockmovement",
            name="warehouse",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="product_cards.warehouse"),
        ),
        migrations.AlterField(
            model_name="materialstockmovement",
            name="movement_type",
            field=models.CharField(choices=[("GIRIS", "Stok Girişi"), ("CIKIS", "Stok Çıkışı"), ("IADE", "İade Girişi"), ("FIRE", "Fire / Zayi"), ("DUZELTME_ARTI", "Sayım Düzeltmesi +"), ("DUZELTME_EKSI", "Sayım Düzeltmesi -"), ("BASLANGIC", "Başlangıç Stoğu"), ("URETIM", "Üretim Tüketimi"), ("URETIM_IADE", "Üretim İadesi"), ("TRANSFER_CIKIS", "Depolar Arası Transfer Çıkışı"), ("TRANSFER_GIRIS", "Depolar Arası Transfer Girişi")], max_length=20),
        ),
        migrations.RunPython(seed_warehouses_and_stocks, noop),
    ]
