from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("core", "0084_instrument_transaction_handover_dates")]
    operations = [
        migrations.CreateModel(
            name="InstrumentPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("side", models.CharField(choices=[("FRONT","Ön"),("BACK","Arka")], max_length=5)),
                ("storage_path", models.CharField(max_length=450)),
                ("original_name", models.CharField(blank=True, default="", max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="core.negotiableinstrument")),
            ],
        ),
        migrations.AddConstraint(model_name="instrumentphoto", constraint=models.UniqueConstraint(fields=("instrument", "side"), name="unique_instrument_photo_side")),
    ]
