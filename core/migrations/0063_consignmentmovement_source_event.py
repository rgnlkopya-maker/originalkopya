from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("core","0062_order_konsinye_type")]
    operations=[
        migrations.AddField(
            model_name="consignmentmovement",
            name="source_event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="consignment_movements",
                to="core.orderevent",
            ),
        ),
    ]
