from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_orderflag"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="orderflag",
            name="detail_note",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="orderflag",
            name="detail_notify_users",
            field=models.ManyToManyField(blank=True, related_name="stage_alert_order_flags", to=settings.AUTH_USER_MODEL),
        ),
    ]
