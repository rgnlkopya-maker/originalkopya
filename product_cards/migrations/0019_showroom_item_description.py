from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("product_cards","0018_showroom_draft")]
    operations=[migrations.AddField(model_name="showroomdraftitem",name="description",field=models.CharField(blank=True,default="",max_length=500))]
