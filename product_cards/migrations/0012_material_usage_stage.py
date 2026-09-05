from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("product_cards","0011_productmaterial_kullanim_asamasi")]
    operations=[migrations.AddField(model_name="material",name="kullanim_asamasi",field=models.CharField(choices=[("KESIM","Kesim Malzemesi"),("SUSLEME","Süsleme Malzemesi")],default="KESIM",max_length=12))]
