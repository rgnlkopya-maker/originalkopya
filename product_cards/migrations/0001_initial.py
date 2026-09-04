from django.db import migrations, models
import django.db.models.deletion


def create_existing_cards(apps, schema_editor):
    UrunKod = apps.get_model("core", "UrunKod")
    ProductCard = apps.get_model("product_cards", "ProductCard")
    for urun in UrunKod.objects.all():
        ProductCard.objects.get_or_create(urun_id=urun.id)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0051_alter_order_siparis_tipi"),
    ]

    operations = [
        migrations.CreateModel(
            name="Material",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kod", models.CharField(max_length=80, unique=True)),
                ("ad", models.CharField(max_length=160)),
                ("birim", models.CharField(choices=[("M", "Metre"), ("ADET", "Adet"), ("KG", "Kilogram"), ("GR", "Gram")], default="M", max_length=10)),
                ("stok_miktari", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("aktif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProductCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("aciklama", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("urun", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="product_card", to="core.urunkod")),
            ],
        ),
        migrations.CreateModel(
            name="ProductMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("miktar", models.DecimalField(decimal_places=3, max_digits=12)),
                ("notlar", models.CharField(blank=True, default="", max_length=255)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_usages", to="product_cards.material")),
                ("product_card", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="materials", to="product_cards.productcard")),
            ],
            options={"ordering": ["material__ad"]},
        ),
        migrations.AddConstraint(
            model_name="productmaterial",
            constraint=models.UniqueConstraint(fields=("product_card", "material"), name="unique_product_material"),
        ),
        migrations.RunPython(create_existing_cards, migrations.RunPython.noop),
    ]
