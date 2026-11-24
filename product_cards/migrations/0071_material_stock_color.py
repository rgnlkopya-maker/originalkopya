from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("product_cards", "0070_restore_white_wedding_124_pending")]
    operations = [
        migrations.AddField(model_name="materialwarehousestock", name="renk", field=models.CharField(max_length=100, blank=True, default="")),
        migrations.AddField(model_name="materialstockmovement", name="renk", field=models.CharField(max_length=100, blank=True, default="")),
        migrations.RemoveConstraint(model_name="materialwarehousestock", name="unique_material_warehouse_stock"),
        migrations.AddConstraint(model_name="materialwarehousestock", constraint=models.UniqueConstraint(fields=("material", "warehouse", "renk"), name="unique_material_warehouse_color")),
        migrations.AlterModelOptions(name="materialwarehousestock", options={"ordering": ["material__ad", "warehouse__ad", "renk"]}),
    ]
