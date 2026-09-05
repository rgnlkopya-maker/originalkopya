from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0052_finance_events_non_status"), ("product_cards", "0009_material_stock_management")]
    operations = [
        migrations.AddField(model_name="materialstockmovement", name="order", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="material_stock_movements", to="core.order")),
        migrations.AddField(model_name="materialstockmovement", name="source_event", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="material_stock_movements", to="core.orderevent")),
        migrations.AddField(model_name="materialstockmovement", name="reversed", field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="materialstockmovement", name="movement_type", field=models.CharField(choices=[("GIRIS", "Stok Girişi"), ("CIKIS", "Stok Çıkışı"), ("IADE", "İade Girişi"), ("FIRE", "Fire / Zayi"), ("DUZELTME_ARTI", "Sayım Düzeltmesi +"), ("DUZELTME_EKSI", "Sayım Düzeltmesi -"), ("BASLANGIC", "Başlangıç Stoğu"), ("URETIM", "Üretim Tüketimi"), ("URETIM_IADE", "Üretim İadesi")], max_length=20)),
    ]
