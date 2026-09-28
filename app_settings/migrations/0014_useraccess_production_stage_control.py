from django.db import migrations, models


def grant_tahir_production_stage_control(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserAccess = apps.get_model("app_settings", "UserAccess")
    user = User.objects.filter(username__iexact="tahir").first()
    if not user:
        return
    access, _ = UserAccess.objects.get_or_create(user_id=user.id)
    access.can_view_production_stage_control = True
    explicit = dict(access.feature_permissions or {})
    explicit["operations.production_stage_control"] = True
    access.feature_permissions = explicit
    access.save(update_fields=["can_view_production_stage_control", "feature_permissions"])


def revoke_tahir_production_stage_control(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserAccess = apps.get_model("app_settings", "UserAccess")
    user = User.objects.filter(username__iexact="tahir").first()
    if not user:
        return
    access = UserAccess.objects.filter(user_id=user.id).first()
    if not access:
        return
    access.can_view_production_stage_control = False
    explicit = dict(access.feature_permissions or {})
    explicit.pop("operations.production_stage_control", None)
    access.feature_permissions = explicit
    access.save(update_fields=["can_view_production_stage_control", "feature_permissions"])


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0013_useraccess_can_share_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccess",
            name="can_view_production_stage_control",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            grant_tahir_production_stage_control,
            revoke_tahir_production_stage_control,
        ),
    ]
