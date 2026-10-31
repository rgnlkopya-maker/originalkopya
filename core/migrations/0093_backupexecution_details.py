from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0092_backup_execution_cursor')]
    operations = [migrations.AddField(model_name='backupexecution', name='details', field=models.JSONField(blank=True, default=list))]
