from django.db import migrations, models


def set_personnel_defaults(apps, schema_editor):
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    User = apps.get_model('auth', 'User')

    # Yalnız normal personel hesaplarını kısıtla. Patron/müdür/superuser mevcut yetkilerini korur.
    manager_ids = set(
        User.objects.filter(groups__name__in=['patron', 'mudur']).values_list('id', flat=True)
    )
    manager_ids.update(User.objects.filter(is_superuser=True).values_list('id', flat=True))

    UserAccess.objects.exclude(user_id__in=manager_ids).update(
        can_view_orders=True,
        can_create_orders=False,
        can_edit_orders=False,
        can_update_production=True,
        can_delete_orders=False,
        can_view_depots=False,
        can_view_reports=False,
        can_view_costs=False,
        can_view_personnel=False,
        can_view_attendance=False,
        can_view_assistant=False,
        can_manage_quality=False,
        can_view_shipping_finance=False,
        can_manage_users=False,
        can_view_settings=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('app_settings', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccess',
            name='can_update_production',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(model_name='useraccess', name='can_create_orders', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='useraccess', name='can_edit_orders', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='useraccess', name='can_view_depots', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='useraccess', name='can_view_attendance', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='useraccess', name='can_view_assistant', field=models.BooleanField(default=False)),
        migrations.AlterField(model_name='useraccess', name='can_manage_quality', field=models.BooleanField(default=False)),
        migrations.RunPython(set_personnel_defaults, migrations.RunPython.noop),
    ]
