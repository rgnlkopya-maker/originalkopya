from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0064_chat_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="chatthread",
            name="pinned_message",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pinned_in_threads", to="core.chatmessage"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="reply_to",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replies", to="core.chatmessage"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="forwarded_from",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forwards", to="core.chatmessage"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="media_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="media_type",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="media_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="edited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ChatMessageEdit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_body", models.TextField(blank=True, default="")),
                ("edited_at", models.DateTimeField(auto_now_add=True)),
                ("edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="edit_history", to="core.chatmessage")),
            ],
            options={"ordering":["edited_at","id"]},
        ),
        migrations.CreateModel(
            name="ChatReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("emoji", models.CharField(max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="core.chatmessage")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_reactions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ChatStar",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stars", to="core.chatmessage")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_stars", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ChatHiddenMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hidden_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hidden_for", to="core.chatmessage")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hidden_chat_messages", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ChatPoll",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.CharField(max_length=300)),
                ("multiple_choice", models.BooleanField(default=False)),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="poll", to="core.chatmessage")),
            ],
        ),
        migrations.CreateModel(
            name="ChatPollOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=200)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("poll", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="core.chatpoll")),
            ],
            options={"ordering":["position","id"]},
        ),
        migrations.CreateModel(
            name="ChatPollVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("option", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="core.chatpolloption")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_poll_votes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="chatreaction",
            constraint=models.UniqueConstraint(fields=("message","user","emoji"), name="unique_chat_reaction"),
        ),
        migrations.AddConstraint(
            model_name="chatstar",
            constraint=models.UniqueConstraint(fields=("message","user"), name="unique_chat_star"),
        ),
        migrations.AddConstraint(
            model_name="chathiddenmessage",
            constraint=models.UniqueConstraint(fields=("message","user"), name="unique_chat_hidden_message"),
        ),
        migrations.AddConstraint(
            model_name="chatpollvote",
            constraint=models.UniqueConstraint(fields=("option","user"), name="unique_chat_poll_option_user"),
        ),
    ]
