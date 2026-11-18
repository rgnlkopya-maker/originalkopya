from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0096_gallery")]
    operations = [migrations.AddField(model_name="gallerymedia", name="sort_order", field=models.PositiveIntegerField(default=0, db_index=True))]
