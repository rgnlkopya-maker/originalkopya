from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0085_instrument_photo")]
    operations = [
        migrations.AddField(model_name="negotiableinstrument", name="next_photo_sequence", field=models.PositiveIntegerField(default=1)),
        migrations.CreateModel(
            name="InstrumentAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("storage_path", models.CharField(max_length=450)),
                ("original_name", models.CharField(blank=True, default="", max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("instrument", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="core.negotiableinstrument")),
            ],
            options={"ordering": ["sequence"]},
        ),
        migrations.AddConstraint(model_name="instrumentattachment", constraint=models.UniqueConstraint(fields=("instrument", "sequence"), name="unique_instrument_attachment_sequence")),
    ]
