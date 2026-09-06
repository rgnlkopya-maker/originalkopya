from django.db import migrations


def grant_tahir_create_orders(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    user = User.objects.filter(username__iexact='tahir').first()
    if user:
        access, _ = UserAccess.objects.get_or_create(user_id=user.id)
        access.can_create_orders = True
        access.save(update_fields=['can_create_orders'])


def revoke_tahir_create_orders(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    user = User.objects.filter(username__iexact='tahir').first()
    if user:
        UserAccess.objects.filter(user_id=user.id).update(can_create_orders=False)


class Migration(migrations.Migration):
    dependencies = [
        ('app_settings', '0004_useraccess_can_manage_planning'),
    ]

    operations = [
        migrations.RunPython(grant_tahir_create_orders, revoke_tahir_create_orders),
    ]
