from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('product_cards', '0045_parasut_oauth_credentials'),
        ('core', '0075_orderflag'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='SmartPatternMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_type', models.CharField(max_length=12, choices=[('ACIK', 'Açık'), ('TESETTUR', 'Tesettür')])),
                ('reference_size', models.CharField(max_length=12, default='38')),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='smart_pattern_master', to='core.urunkod')),
            ],
            options={'ordering': ['product__kod']},
        ),
    ]
