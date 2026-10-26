from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0078_assistantconversation")]
    operations = [
        migrations.AddField(model_name="customerdetail", name="resmi_unvan", field=models.CharField(max_length=250, blank=True, default="")),
        migrations.AddField(model_name="customerdetail", name="vergi_dairesi", field=models.CharField(max_length=120, blank=True, default="")),
        migrations.AddField(model_name="customerdetail", name="vergi_numarasi", field=models.CharField(max_length=30, blank=True, default="")),
        migrations.AddField(model_name="customerdetail", name="mersis_no", field=models.CharField(max_length=40, blank=True, default="")),
        migrations.AddField(model_name="customerdetail", name="ticaret_sicil_no", field=models.CharField(max_length=50, blank=True, default="")),
        migrations.AddField(model_name="customerdetail", name="posta_kodu", field=models.CharField(max_length=20, blank=True, default="")),
    ]
