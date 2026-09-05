from django.conf import settings
from django.db import migrations


def delete_legacy_users(apps, schema_editor):
    User = apps.get_model("auth", "User")
    OrderEvent = apps.get_model("core", "OrderEvent")

    usernames = ["Mehmet", "patron"]

    # OrderEvent.user is stored as text, so these activity rows must be removed explicitly.
    OrderEvent.objects.filter(user__in=usernames).delete()

    # Related FK/OneToOne records (profiles, attendance, groups, sessions-related user links, etc.)
    # are collected by Django when the user rows are deleted.
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0006_employeehrprofile_personal_fields"),
        ("core", "0052_finans_hareketlerini_son_durumdan_ayir"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(delete_legacy_users, migrations.RunPython.noop),
    ]
