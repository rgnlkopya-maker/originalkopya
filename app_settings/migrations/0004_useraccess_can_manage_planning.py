from django.db import migrations, models


def grant_tahir_planning(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    user = User.objects.filter(username__iexact='tahir').first()
    if user:
        access, _ = UserAccess.objects.get_or_create(user_id=user.id)
        access.can_manage_planning = True
        access.save(update_fields=['can_manage_planning'])


def revoke_tahir_planning(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserAccess = apps.get_model('app_settings', 'UserAccess')
    user = User.objects.filter(username__iexact='tahir').first()
    if user:
        UserAccess.objects.filter(user_id=user.id).update(can_manage_planning=False)


class Migration(migrations.Migration):
    dependencies = [
        ('app_settings', '0003_systemsettings_active_depots'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccess',
            name='can_manage_planning',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(grant_tahir_planning, revoke_tahir_planning),
    ]
