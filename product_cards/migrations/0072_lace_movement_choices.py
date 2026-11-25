from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("product_cards", "0071_material_stock_color")]
    operations = [
        migrations.AlterField(model_name="materialstockmovement", name="movement_type", field=models.CharField(max_length=20, choices=[("GIRIS","Stok Girişi"),("CIKIS","Stok Çıkışı"),("IADE","İade Girişi"),("FIRE","Fire / Zayi"),("DUZELTME_ARTI","Sayım Düzeltmesi +"),("DUZELTME_EKSI","Sayım Düzeltmesi -"),("BASLANGIC","Başlangıç Stoğu"),("URETIM","Üretim Tüketimi"),("URETIM_IADE","Üretim İadesi"),("DANTEL_AYIR","Siparişe Dantel Ayrıldı"),("DANTEL_IADE","Dantel İadesi"),("TRANSFER_CIKIS","Depolar Arası Transfer Çıkışı"),("TRANSFER_GIRIS","Depolar Arası Transfer Girişi")])),
    ]
