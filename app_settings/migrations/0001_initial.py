from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_access(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    for user in User.objects.all():
        groups = set(user.groups.values_list('name', flat=True))
        manager = user.is_superuser or bool(groups.intersection({'patron', 'mudur'}))
        defaults = {
            'can_view_orders': True,
            'can_create_orders': True,
            'can_edit_orders': True,
            'can_delete_orders': manager,
            'can_view_depots': True,
            'can_view_reports': manager,
            'can_view_costs': manager,
            'can_view_personnel': manager,
            'can_view_attendance': True,
            'can_view_assistant': True,
            'can_manage_quality': True,
            'can_view_shipping_finance': manager,
            'can_manage_users': manager,
            'can_view_settings': manager,
        }
        UserAccess.objects.get_or_create(user_id=user.id, defaults=defaults)


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(default='Moli Tekstil', max_length=160)),
                ('company_phone', models.CharField(blank=True, default='', max_length=40)),
                ('company_email', models.EmailField(blank=True, default='', max_length=254)),
                ('company_address', models.TextField(blank=True, default='')),
                ('default_order_type', models.CharField(choices=[('SERI','Seri'),('TEKLI','Tekli Sipariş'),('STOK','Stoğa Üretim'),('OZEL','Özel Sipariş')], default='SERI', max_length=20)),
                ('default_delivery_days', models.PositiveIntegerField(default=30)),
                ('default_currency', models.CharField(choices=[('TRY','TRY'),('USD','USD'),('EUR','EUR')], default='TRY', max_length=3)),
                ('tcmb_update_hour', models.PositiveSmallIntegerField(default=9)),
                ('finance_enabled', models.BooleanField(default=True)),
                ('quality_categories', models.TextField(default='Dikiş hatası\nÖlçü / beden\nKumaş\nSüsleme\nLeke\nYanlış ürün\nPaketleme\nDiğer')),
                ('notify_late_orders', models.BooleanField(default=True)),
                ('notify_upcoming_delivery', models.BooleanField(default=True)),
                ('notify_open_quality_issue', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_view_orders', models.BooleanField(default=True)),
                ('can_create_orders', models.BooleanField(default=True)),
                ('can_edit_orders', models.BooleanField(default=True)),
                ('can_delete_orders', models.BooleanField(default=False)),
                ('can_view_depots', models.BooleanField(default=True)),
                ('can_view_reports', models.BooleanField(default=False)),
                ('can_view_costs', models.BooleanField(default=False)),
                ('can_view_personnel', models.BooleanField(default=False)),
                ('can_view_attendance', models.BooleanField(default=True)),
                ('can_view_assistant', models.BooleanField(default=True)),
                ('can_manage_quality', models.BooleanField(default=True)),
                ('can_view_shipping_finance', models.BooleanField(default=False)),
                ('can_manage_users', models.BooleanField(default=False)),
                ('can_view_settings', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='moli_access', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(seed_access, migrations.RunPython.noop),
    ]
