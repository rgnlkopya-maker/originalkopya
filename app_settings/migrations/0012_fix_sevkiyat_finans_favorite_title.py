from django.db import migrations


def fix_sevkiyat_finans_favorite_title(apps, schema_editor):
    UserFavorite = apps.get_model("app_settings", "UserFavorite")
    UserFavorite.objects.filter(
        path="/reports/sevkiyat-finans/",
        title="Bekleyen Hatırlatmalar",
    ).update(title="Sevkiyat Finans")


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0011_userfavorite"),
    ]

    operations = [
        migrations.RunPython(
            fix_sevkiyat_finans_favorite_title,
            migrations.RunPython.noop,
        ),
    ]
