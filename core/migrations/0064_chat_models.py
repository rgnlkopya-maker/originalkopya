from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0063_consignmentmovement_source_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatThread",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("thread_type", models.CharField(choices=[("direct","Birebir"),("group","Grup")], db_index=True, default="direct", max_length=10)),
                ("name", models.CharField(blank=True, default="", max_length=160)),
                ("direct_key", models.CharField(blank=True, max_length=80, null=True, unique=True)),
                ("only_admins_can_message", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_chat_threads", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-updated_at","-id"]},
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("importance", models.CharField(choices=[("normal","Normal"),("important","Önemli"),("urgent","Acil")], default="normal", max_length=10)),
                ("linked_path", models.CharField(blank=True, default="", max_length=500)),
                ("linked_label", models.CharField(blank=True, default="", max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("sender", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_chat_messages", to=settings.AUTH_USER_MODEL)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="core.chatthread")),
            ],
            options={"ordering":["created_at","id"]},
        ),
        migrations.CreateModel(
            name="ChatMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_admin", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="core.chatthread")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ChatReadState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_read_at", models.DateTimeField(blank=True, null=True)),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="read_states", to="core.chatthread")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_read_states", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="chatmembership",
            constraint=models.UniqueConstraint(fields=("thread","user"), name="unique_chat_thread_user"),
        ),
        migrations.AddConstraint(
            model_name="chatreadstate",
            constraint=models.UniqueConstraint(fields=("thread","user"), name="unique_chat_read_state"),
        ),
    ]
