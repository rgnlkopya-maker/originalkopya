from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0073_production_stage_control_exclusion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderNoticeRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notice_hash", models.CharField(max_length=64)),
                ("read_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notice_reads", to="core.order")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_notice_reads", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="ordernoticeread",
            constraint=models.UniqueConstraint(fields=("user", "order"), name="uniq_order_notice_read_user_order"),
        ),
        migrations.AddIndex(
            model_name="ordernoticeread",
            index=models.Index(fields=["order", "notice_hash"], name="core_ordernot_order_i_6baaf2_idx"),
        ),
        migrations.AddIndex(
            model_name="ordernoticeread",
            index=models.Index(fields=["user", "read_at"], name="core_ordernot_user_id_19d86a_idx"),
        ),
    ]
