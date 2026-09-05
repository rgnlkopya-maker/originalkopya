from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0052_finans_hareketlerini_son_durumdan_ayir"),
        ("product_cards", "0013_warehouse_stock"),
    ]
    operations = [
        migrations.CreateModel(
            name="ProductWarehouseStock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_stocks", to="core.urunkod")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_stocks", to="product_cards.warehouse")),
            ],
            options={"ordering": ["product__kod"]},
        ),
        migrations.AddConstraint(model_name="productwarehousestock", constraint=models.UniqueConstraint(fields=("product", "warehouse"), name="unique_product_warehouse_stock")),
        migrations.CreateModel(
            name="ProductStockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("GIRIS", "Stok Girişi"), ("CIKIS", "Stok Çıkışı"), ("IADE", "İade Girişi"), ("DUZELTME_ARTI", "Sayım Düzeltmesi +"), ("DUZELTME_EKSI", "Sayım Düzeltmesi -")], max_length=20)),
                ("quantity", models.PositiveIntegerField()),
                ("previous_stock", models.PositiveIntegerField(default=0)),
                ("resulting_stock", models.PositiveIntegerField(default=0)),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_movements", to="core.urunkod")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_movements", to="product_cards.warehouse")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
