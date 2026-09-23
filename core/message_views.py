import os
import uuid
from collections import Counter

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from supabase import create_client

from .push_views import send_chat_push

from .models import (
    ChatThread, ChatMembership, ChatMessage, ChatReadState,
    ChatMessageEdit, ChatReaction, ChatStar, ChatHiddenMessage,
    ChatPoll, ChatPollOption, ChatPollVote,
)


ALLOWED_MEDIA_TYPES = {
    "image/jpeg": "image", "image/png": "image", "image/webp": "image", "image/heic": "image",
    "video/mp4": "video", "video/quicktime": "video", "video/webm": "video",
    "audio/webm": "audio", "audio/mp4": "audio", "audio/mpeg": "audio", "audio/ogg": "audio", "audio/wav": "audio",
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "text/plain": "document",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _membership_or_403(user, thread):
    return ChatMembership.objects.filter(thread=thread, user=user).first()


def _thread_title(thread, viewer):
    if thread.thread_type == "group":
        return thread.name or "Grup"
    other = (
        ChatMembership.objects.filter(thread=thread)
        .exclude(user=viewer)
        .select_related("user")
        .first()
    )
    if not other:
        return "Sohbet"
    return other.user.get_full_name() or other.user.username


def _can_send(user, thread):
    membership = _membership_or_403(user, thread)
    if not membership:
        return False
    if thread.thread_type == "group" and thread.only_admins_can_message and not membership.is_admin:
        return False
    return True


def _upload_chat_media(uploaded_file, thread_id):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Kalıcı medya depolama ayarları eksik.")
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValueError("Dosya boyutu 25 MB sınırını aşıyor.")

    content_type = (uploaded_file.content_type or "application/octet-stream").lower()
    media_type = ALLOWED_MEDIA_TYPES.get(content_type)
    if not media_type:
        if content_type.startswith("image/"):
            media_type = "image"
        elif content_type.startswith("video/"):
            media_type = "video"
        elif content_type.startswith("audio/"):
            media_type = "audio"
        else:
            raise ValueError("Bu dosya türü desteklenmiyor.")

    ext = os.path.splitext(uploaded_file.name or "")[1].lower()
    if not ext:
        ext = {"image": ".jpg", "video": ".mp4", "audio": ".webm", "document": ".bin"}[media_type]
    path = f"chat-media/{thread_id}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
    uploaded_file.seek(0)
    bucket.upload(
        path,
        uploaded_file.read(),
        file_options={"content-type": content_type, "upsert": "false"},
    )
    return bucket.get_public_url(path), media_type


def _message_read_by_all(message):
    member_ids = list(
        ChatMembership.objects.filter(thread=message.thread)
        .exclude(user_id=message.sender_id)
        .values_list("user_id", flat=True)
    )
    if not member_ids:
        return True
    states = {
        state.user_id: state.last_read_at
        for state in ChatReadState.objects.filter(thread=message.thread, user_id__in=member_ids)
    }
    return all(states.get(uid) and states[uid] >= message.created_at for uid in member_ids)


def _serialize_poll(message, viewer):
    try:
        poll = message.poll
    except Exception:
        return None
    options = list(poll.options.prefetch_related("votes").all())
    my_votes = set(
        ChatPollVote.objects.filter(option__poll=poll, user=viewer).values_list("option_id", flat=True)
    )
    return {
        "id": poll.id,
        "question": poll.question,
        "multiple_choice": poll.multiple_choice,
        "options": [
            {
                "id": option.id,
                "text": option.text,
                "votes": option.votes.count(),
                "mine": option.id in my_votes,
            }
            for option in options
        ],
    }


def _serialize_message(message, viewer):
    reactions = list(message.reactions.select_related("user").all())
    counts = Counter(r.emoji for r in reactions)
    mine_reactions = {r.emoji for r in reactions if r.user_id == viewer.id}
    starred = ChatStar.objects.filter(message=message, user=viewer).exists()
    hidden = ChatHiddenMessage.objects.filter(message=message, user=viewer).exists()

    reply = None
    if message.reply_to_id:
        original = message.reply_to
        reply = {
            "id": original.id,
            "sender": (
                original.sender.get_full_name() or original.sender.username
                if original.sender else "Silinmiş kullanıcı"
            ),
            "body": "Mesaj silindi" if original.is_deleted else (original.body or original.media_name or "Medya"),
        }

    seen_by = []
    if message.sender_id == viewer.id:
        reader_ids = list(
            ChatMembership.objects.filter(thread=message.thread)
            .exclude(user_id=message.sender_id)
            .values_list("user_id", flat=True)
        )
        if reader_ids:
            states = {
                state.user_id: state.last_read_at
                for state in ChatReadState.objects.filter(
                    thread=message.thread,
                    user_id__in=reader_ids,
                    last_read_at__gte=message.created_at,
                ).select_related("user")
            }
            users = {
                u.id: u
                for u in User.objects.filter(id__in=states.keys())
            }
            for uid in reader_ids:
                state = states.get(uid)
                user_obj = users.get(uid)
                if state and user_obj:
                    seen_by.append({
                        "id": uid,
                        "name": user_obj.get_full_name() or user_obj.username,
                        "seen_at": timezone.localtime(state).strftime("%d.%m.%Y %H:%M"),
                    })

    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender": (
            (message.sender.get_full_name() or message.sender.username)
            if message.sender else "Silinmiş kullanıcı"
        ),
        "body": "" if message.is_deleted else message.body,
        "is_deleted": message.is_deleted,
        "importance": message.importance,
        "linked_path": "" if message.is_deleted else message.linked_path,
        "linked_label": "" if message.is_deleted else message.linked_label,
        "media_url": "" if message.is_deleted else message.media_url,
        "media_type": "" if message.is_deleted else message.media_type,
        "media_name": "" if message.is_deleted else message.media_name,
        "reply": reply,
        "forwarded": bool(message.forwarded_from_id),
        "edited": bool(message.edited_at),
        "created_at": timezone.localtime(message.created_at).strftime("%d.%m.%Y %H:%M"),
        "time": timezone.localtime(message.created_at).strftime("%H:%M"),
        "mine": message.sender_id == viewer.id,
        "read": _message_read_by_all(message) if message.sender_id == viewer.id else False,
        "seen_by": seen_by,
        "seen_count": len(seen_by),
        "starred": starred,
        "hidden": hidden,
        "reactions": [
            {"emoji": emoji, "count": count, "mine": emoji in mine_reactions}
            for emoji, count in counts.items()
        ],
        "poll": None if message.is_deleted else _serialize_poll(message, viewer),
        "can_edit": message.sender_id == viewer.id and not message.is_deleted and bool(message.body),
        "can_delete_everyone": message.sender_id == viewer.id and not message.is_deleted,
    }


@login_required
@never_cache
def messages_home(request, thread_id=None):
    memberships = list(
        ChatMembership.objects.filter(user=request.user)
        .select_related("thread")
        .order_by("-thread__updated_at")
    )
    active_thread = None
    active_membership = None

    force_list = request.GET.get("list") == "1"
    if thread_id and not force_list:
        active_thread = get_object_or_404(ChatThread, pk=thread_id)
        active_membership = _membership_or_403(request.user, active_thread)
        if not active_membership:
            return HttpResponseForbidden("Bu sohbete erişiminiz yok.")

    thread_rows = []
    for membership in memberships:
        thread = membership.thread
        state = ChatReadState.objects.filter(thread=thread, user=request.user).first()
        unread_qs = ChatMessage.objects.filter(thread=thread, is_deleted=False).exclude(sender=request.user)
        if state and state.last_read_at:
            unread_qs = unread_qs.filter(created_at__gt=state.last_read_at)
        last_message = thread.messages.order_by("-created_at", "-id").first()
        thread_rows.append({
            "thread": thread,
            "title": _thread_title(thread, request.user),
            "unread": unread_qs.count(),
            "last_message": last_message,
        })

    active_messages = []
    active_members = []
    if active_thread:
        hidden_ids = ChatHiddenMessage.objects.filter(
            user=request.user, message__thread=active_thread
        ).values_list("message_id", flat=True)
        active_messages = list(
            active_thread.messages.exclude(id__in=hidden_ids)
            .select_related("sender", "reply_to", "reply_to__sender", "forwarded_from")
            .prefetch_related("reactions", "reactions__user")
            .order_by("created_at", "id")[:300]
        )
        ChatReadState.objects.update_or_create(
            thread=active_thread,
            user=request.user,
            defaults={"last_read_at": timezone.now()},
        )
        active_members = list(
            ChatMembership.objects.filter(thread=active_thread)
            .select_related("user")
            .order_by("-is_admin", "user__first_name", "user__username")
        )

    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by(
        "first_name", "last_name", "username"
    )

    return render(request, "messages/home.html", {
        "thread_rows": thread_rows,
        "active_thread": active_thread,
        "active_title": _thread_title(active_thread, request.user) if active_thread else "",
        "active_membership": active_membership,
        "active_messages": active_messages,
        "active_members": active_members,
        "users": users,
        "pinned_message": active_thread.pinned_message if active_thread else None,
    })


@login_required
@require_POST
def start_direct(request):
    target = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True)
    if target.id == request.user.id:
        return redirect("messages_home")
    a, b = sorted([request.user.id, target.id])
    direct_key = f"{a}:{b}"
    with transaction.atomic():
        thread, _ = ChatThread.objects.get_or_create(
            direct_key=direct_key,
            defaults={"thread_type": "direct", "created_by": request.user},
        )
        ChatMembership.objects.get_or_create(thread=thread, user=request.user)
        ChatMembership.objects.get_or_create(thread=thread, user=target)
    return redirect("messages_thread", thread_id=thread.id)


@login_required
@require_POST
def create_group(request):
    name = (request.POST.get("name") or "").strip()[:160] or "Yeni Grup"
    member_ids = []
    for raw in request.POST.getlist("member_ids"):
        try:
            member_ids.append(int(raw))
        except (TypeError, ValueError):
            pass
    with transaction.atomic():
        thread = ChatThread.objects.create(thread_type="group", name=name, created_by=request.user)
        ChatMembership.objects.create(thread=thread, user=request.user, is_admin=True)
        for user in User.objects.filter(id__in=member_ids, is_active=True).exclude(pk=request.user.pk):
            ChatMembership.objects.get_or_create(thread=thread, user=user)
    return redirect("messages_thread", thread_id=thread.id)


@login_required
@require_POST
def send_message(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _can_send(request.user, thread):
        return JsonResponse({"ok": False, "message": "Bu sohbette mesaj gönderme yetkiniz yok."}, status=403)

    body = (request.POST.get("body") or "").strip()
    importance = (request.POST.get("importance") or "normal").strip()
    if importance not in {"normal", "important", "urgent"}:
        importance = "normal"

    reply_to = None
    reply_id = request.POST.get("reply_to")
    if reply_id:
        reply_to = ChatMessage.objects.filter(pk=reply_id, thread=thread).first()

    linked_path = (request.POST.get("linked_path") or "").strip()[:500]
    linked_label = (request.POST.get("linked_label") or "").strip()[:180]
    if linked_path and not (
        (linked_path.startswith("/") and not linked_path.startswith("//"))
        or linked_path.startswith("https://")
    ):
        linked_path = ""
        linked_label = ""

    upload = request.FILES.get("media")
    media_url = media_type = media_name = ""
    if upload:
        try:
            media_url, media_type = _upload_chat_media(upload, thread.id)
            media_name = (upload.name or "Dosya")[:255]
        except (ValueError, RuntimeError) as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)
        except Exception:
            return JsonResponse({"ok": False, "message": "Dosya yüklenemedi."}, status=500)

    if not body and not media_url and not linked_path:
        return JsonResponse({"ok": False, "message": "Mesaj boş olamaz."}, status=400)

    message = ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        body=body,
        importance=importance,
        linked_path=linked_path,
        linked_label=linked_label,
        reply_to=reply_to,
        media_url=media_url,
        media_type=media_type,
        media_name=media_name,
    )
    ChatThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    ChatReadState.objects.update_or_create(
        thread=thread, user=request.user, defaults={"last_read_at": timezone.now()}
    )
    send_chat_push(message)
    return JsonResponse({"ok": True, "message": _serialize_message(message, request.user)})


@login_required
@require_GET
def thread_messages(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _membership_or_403(request.user, thread):
        return JsonResponse({"ok": False}, status=403)
    hidden_ids = ChatHiddenMessage.objects.filter(
        user=request.user, message__thread=thread
    ).values_list("message_id", flat=True)
    messages = list(
        thread.messages.exclude(id__in=hidden_ids)
        .select_related("sender", "reply_to", "reply_to__sender", "forwarded_from")
        .prefetch_related("reactions", "reactions__user")
        .order_by("-created_at", "-id")[:150]
    )
    messages.reverse()
    ChatReadState.objects.update_or_create(
        thread=thread, user=request.user, defaults={"last_read_at": timezone.now()}
    )
    return JsonResponse({
        "ok": True,
        "pinned_message_id": thread.pinned_message_id,
        "messages": [_serialize_message(m, request.user) for m in messages],
    })


@login_required
@require_GET
def unread_count(request):
    memberships = list(ChatMembership.objects.filter(user=request.user).values_list("thread_id", flat=True))
    states = {
        s.thread_id: s.last_read_at
        for s in ChatReadState.objects.filter(user=request.user, thread_id__in=memberships)
    }
    total = 0
    for thread_id in memberships:
        qs = ChatMessage.objects.filter(thread_id=thread_id, is_deleted=False).exclude(sender=request.user)
        last_read = states.get(thread_id)
        if last_read:
            qs = qs.filter(created_at__gt=last_read)
        total += qs.count()
    return JsonResponse({"ok": True, "count": total})


@login_required
@require_POST
def message_action(request, message_id):
    message = get_object_or_404(
        ChatMessage.objects.select_related("thread", "sender"),
        pk=message_id,
    )
    membership = _membership_or_403(request.user, message.thread)
    if not membership:
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)

    action = (request.POST.get("action") or "").strip()

    if action == "edit":
        if message.sender_id != request.user.id or message.is_deleted:
            return JsonResponse({"ok": False, "message": "Bu mesajı düzenleyemezsiniz."}, status=403)
        new_body = (request.POST.get("body") or "").strip()
        if not new_body:
            return JsonResponse({"ok": False, "message": "Mesaj boş olamaz."}, status=400)
        ChatMessageEdit.objects.create(message=message, edited_by=request.user, old_body=message.body)
        message.body = new_body
        message.edited_at = timezone.now()
        message.save(update_fields=["body", "edited_at"])
    elif action == "delete_me":
        ChatHiddenMessage.objects.get_or_create(message=message, user=request.user)
    elif action == "delete_everyone":
        if message.sender_id != request.user.id:
            return JsonResponse({"ok": False, "message": "Bu mesajı herkesten silemezsiniz."}, status=403)
        message.is_deleted = True
        message.deleted_at = timezone.now()
        message.save(update_fields=["is_deleted", "deleted_at"])
    elif action == "star":
        star = ChatStar.objects.filter(message=message, user=request.user).first()
        if star:
            star.delete()
        else:
            ChatStar.objects.create(message=message, user=request.user)
    elif action == "react":
        emoji = (request.POST.get("emoji") or "").strip()[:16]
        if not emoji:
            return JsonResponse({"ok": False}, status=400)
        reaction = ChatReaction.objects.filter(message=message, user=request.user, emoji=emoji).first()
        if reaction:
            reaction.delete()
        else:
            ChatReaction.objects.create(message=message, user=request.user, emoji=emoji)
    elif action == "pin":
        if message.thread.thread_type == "group" and not membership.is_admin:
            return JsonResponse({"ok": False, "message": "Grup mesajını yalnız yöneticiler sabitleyebilir."}, status=403)
        message.thread.pinned_message = None if message.thread.pinned_message_id == message.id else message
        message.thread.save(update_fields=["pinned_message", "updated_at"])
    else:
        return JsonResponse({"ok": False, "message": "Geçersiz işlem."}, status=400)

    refreshed = ChatMessage.objects.select_related(
        "sender", "reply_to", "reply_to__sender", "forwarded_from"
    ).prefetch_related("reactions", "reactions__user").get(pk=message.pk)
    return JsonResponse({"ok": True, "message": _serialize_message(refreshed, request.user)})


@login_required
@require_POST
def forward_message(request, message_id):
    source = get_object_or_404(ChatMessage, pk=message_id)
    if not _membership_or_403(request.user, source.thread):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)
    target = get_object_or_404(ChatThread, pk=request.POST.get("thread_id"))
    if not _can_send(request.user, target):
        return JsonResponse({"ok": False, "message": "Hedef sohbete mesaj gönderemezsiniz."}, status=403)

    message = ChatMessage.objects.create(
        thread=target,
        sender=request.user,
        body=source.body,
        importance=source.importance,
        linked_path=source.linked_path,
        linked_label=source.linked_label,
        media_url=source.media_url,
        media_type=source.media_type,
        media_name=source.media_name,
        forwarded_from=source,
    )
    ChatThread.objects.filter(pk=target.pk).update(updated_at=timezone.now())
    return JsonResponse({"ok": True, "thread_id": target.id, "message_id": message.id})


@login_required
@require_POST
def create_poll(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _can_send(request.user, thread):
        return JsonResponse({"ok": False, "message": "Yetkiniz yok."}, status=403)
    question = (request.POST.get("question") or "").strip()[:300]
    options = [x.strip()[:200] for x in request.POST.getlist("options") if x.strip()]
    if not question or len(options) < 2:
        return JsonResponse({"ok": False, "message": "Anket için soru ve en az iki seçenek gerekli."}, status=400)
    with transaction.atomic():
        message = ChatMessage.objects.create(thread=thread, sender=request.user, body="")
        poll = ChatPoll.objects.create(
            message=message,
            question=question,
            multiple_choice=request.POST.get("multiple_choice") == "1",
        )
        for index, option in enumerate(options[:10]):
            ChatPollOption.objects.create(poll=poll, text=option, position=index)
        ChatThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    return JsonResponse({"ok": True, "message_id": message.id})


@login_required
@require_POST
def vote_poll(request, option_id):
    option = get_object_or_404(ChatPollOption.objects.select_related("poll__message__thread"), pk=option_id)
    poll = option.poll
    if not _membership_or_403(request.user, poll.message.thread):
        return JsonResponse({"ok": False}, status=403)
    existing = ChatPollVote.objects.filter(option=option, user=request.user).first()
    if existing:
        existing.delete()
    else:
        if not poll.multiple_choice:
            ChatPollVote.objects.filter(option__poll=poll, user=request.user).delete()
        ChatPollVote.objects.create(option=option, user=request.user)
    return JsonResponse({"ok": True})


@login_required
@require_GET
def search_messages(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _membership_or_403(request.user, thread):
        return JsonResponse({"ok": False}, status=403)
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"ok": True, "results": []})
    hidden_ids = ChatHiddenMessage.objects.filter(user=request.user, message__thread=thread).values_list("message_id", flat=True)
    rows = (
        ChatMessage.objects.filter(thread=thread, is_deleted=False)
        .exclude(id__in=hidden_ids)
        .filter(Q(body__icontains=q) | Q(linked_label__icontains=q) | Q(media_name__icontains=q))
        .select_related("sender")
        .order_by("-created_at")[:50]
    )
    return JsonResponse({
        "ok": True,
        "results": [
            {
                "id": m.id,
                "sender": (m.sender.get_full_name() or m.sender.username) if m.sender else "",
                "body": m.body or m.media_name or m.linked_label,
                "created_at": timezone.localtime(m.created_at).strftime("%d.%m.%Y %H:%M"),
            }
            for m in rows
        ],
    })


@login_required
@require_GET
def starred_messages(request):
    rows = (
        ChatStar.objects.filter(user=request.user)
        .select_related("message", "message__thread", "message__sender")
        .order_by("-created_at")[:200]
    )
    data = [
        {
            "message_id": row.message_id,
            "thread_id": row.message.thread_id,
            "thread_title": _thread_title(row.message.thread, request.user),
            "body": row.message.body or row.message.media_name or "Mesaj",
            "created_at": timezone.localtime(row.message.created_at).strftime("%d.%m.%Y %H:%M"),
        }
        for row in rows
        if _membership_or_403(request.user, row.message.thread)
    ]
    return JsonResponse({"ok": True, "results": data})


@login_required
@require_POST
def share_contact(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _can_send(request.user, thread):
        return JsonResponse({"ok": False}, status=403)
    target = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True)
    label = target.get_full_name() or target.username
    body = f"👤 Kişi: {label}\nKullanıcı adı: @{target.username}"
    message = ChatMessage.objects.create(thread=thread, sender=request.user, body=body)
    ChatThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    return JsonResponse({"ok": True, "message_id": message.id})


@login_required
@require_POST
def group_manage(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id, thread_type="group")
    membership = _membership_or_403(request.user, thread)
    if not membership or not membership.is_admin:
        return HttpResponseForbidden("Bu işlem için grup yöneticisi olmalısınız.")

    action = request.POST.get("action")
    if action == "rename":
        name = (request.POST.get("name") or "").strip()[:160]
        if name:
            thread.name = name
            thread.save(update_fields=["name", "updated_at"])
    elif action == "toggle_only_admins":
        thread.only_admins_can_message = not thread.only_admins_can_message
        thread.save(update_fields=["only_admins_can_message", "updated_at"])
    elif action == "add_member":
        user = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True)
        ChatMembership.objects.get_or_create(thread=thread, user=user)
    elif action == "remove_member":
        target = get_object_or_404(ChatMembership, thread=thread, user_id=request.POST.get("user_id"))
        if target.user_id != request.user.id:
            target.delete()
    elif action == "toggle_admin":
        target = get_object_or_404(ChatMembership, thread=thread, user_id=request.POST.get("user_id"))
        if target.user_id != request.user.id:
            target.is_admin = not target.is_admin
            target.save(update_fields=["is_admin"])
    return redirect("messages_thread", thread_id=thread.id)
