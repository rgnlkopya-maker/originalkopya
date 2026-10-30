from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0091_backup_center")]
    operations = [migrations.AddField(model_name="backupexecution", name="cursor", field=models.PositiveIntegerField(default=0))]
