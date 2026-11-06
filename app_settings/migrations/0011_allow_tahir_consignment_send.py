from django.db import migrations


def allow_tahir_consignment_send(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserAccess = apps.get_model("app_settings", "UserAccess")
    user = User.objects.filter(pk=8, username__iexact="tahir").first()
    if user is None:
        return
    access, _ = UserAccess.objects.get_or_create(user_id=user.pk)
    permissions = dict(access.feature_permissions or {})
    if permissions.get("consignment.send") is True:
        return
    permissions["consignment.send"] = True
    access.feature_permissions = permissions
    access.save(update_fields=["feature_permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0014_useraccess_production_stage_control"),
    ]

    operations = [
        migrations.RunPython(allow_tahir_consignment_send, migrations.RunPython.noop),
    ]
