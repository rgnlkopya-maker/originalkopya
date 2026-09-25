import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("attendance", "0013_five_minute_late_tolerance")]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="checkout_forgotten",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="checkout_forgotten_resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="checkout_forgotten_resolved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resolved_forgotten_checkouts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
