from django.db import migrations, models


def move_modelleme_staff(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    UserProfile.objects.filter(user__username__in=["Esma", "Mihriban"]).update(gorev="modelleme")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0052_finans_hareketlerini_son_durumdan_ayir"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="gorev",
            field=models.CharField(
                choices=[
                    ("yok", "Yok"),
                    ("kesim", "Kesim"),
                    ("dikim", "Dikim"),
                    ("modelleme", "Modelleme"),
                    ("susleme", "Süsleme"),
                    ("hazir", "Hazır"),
                    ("sevkiyat", "Sevkiyat"),
                    ("nakis", "Nakış"),
                ],
                default="yok",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="orderevent",
            name="gorev",
            field=models.CharField(
                choices=[
                    ("yok", "Yok"),
                    ("kesim", "Kesim"),
                    ("dikim", "Dikim"),
                    ("modelleme", "Modelleme"),
                    ("susleme", "Süsleme"),
                    ("hazir", "Hazır"),
                    ("sevkiyat", "Sevkiyat"),
                    ("nakis", "Nakış"),
                ],
                default="yok",
                max_length=20,
            ),
        ),
        migrations.RunPython(move_modelleme_staff, migrations.RunPython.noop),
    ]
