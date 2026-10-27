from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0071_todoitem")]
    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="system_frozen",
            field=models.BooleanField(default=False),
        ),
    ]
