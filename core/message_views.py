from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import ChatThread, ChatMembership, ChatMessage, ChatReadState


def _membership_or_403(user, thread):
    membership = ChatMembership.objects.filter(thread=thread, user=user).first()
    if not membership:
        return None
    return membership


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


def _serialize_message(message, viewer):
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
        "linked_path": message.linked_path,
        "linked_label": message.linked_label,
        "created_at": timezone.localtime(message.created_at).strftime("%d.%m.%Y %H:%M"),
        "mine": message.sender_id == viewer.id,
    }


@login_required
def messages_home(request, thread_id=None):
    memberships = list(
        ChatMembership.objects
        .filter(user=request.user)
        .select_related("thread")
        .order_by("-thread__updated_at")
    )
    active_thread = None
    active_membership = None

    if thread_id:
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
        unread = unread_qs.count()
        last_message = thread.messages.order_by("-created_at", "-id").first()
        thread_rows.append({
            "thread": thread,
            "title": _thread_title(thread, request.user),
            "unread": unread,
            "last_message": last_message,
        })

    active_messages = []
    active_members = []
    if active_thread:
        active_messages = list(
            active_thread.messages.select_related("sender").order_by("created_at", "id")[:300]
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

    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by("first_name", "last_name", "username")

    return render(request, "messages/home.html", {
        "thread_rows": thread_rows,
        "active_thread": active_thread,
        "active_title": _thread_title(active_thread, request.user) if active_thread else "",
        "active_membership": active_membership,
        "active_messages": active_messages,
        "active_members": active_members,
        "users": users,
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
            defaults={
                "thread_type": "direct",
                "created_by": request.user,
            },
        )
        ChatMembership.objects.get_or_create(thread=thread, user=request.user)
        ChatMembership.objects.get_or_create(thread=thread, user=target)
    return redirect("messages_thread", thread_id=thread.id)


@login_required
@require_POST
def create_group(request):
    name = (request.POST.get("name") or "").strip()[:160]
    if not name:
        name = "Yeni Grup"

    member_ids = []
    for raw in request.POST.getlist("member_ids"):
        try:
            member_ids.append(int(raw))
        except (TypeError, ValueError):
            pass

    with transaction.atomic():
        thread = ChatThread.objects.create(
            thread_type="group",
            name=name,
            created_by=request.user,
        )
        ChatMembership.objects.create(thread=thread, user=request.user, is_admin=True)
        for user in User.objects.filter(id__in=member_ids, is_active=True).exclude(pk=request.user.pk):
            ChatMembership.objects.get_or_create(thread=thread, user=user)
    return redirect("messages_thread", thread_id=thread.id)


@login_required
@require_POST
def send_message(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    membership = _membership_or_403(request.user, thread)
    if not membership:
        return JsonResponse({"ok": False, "message": "Bu sohbete erişiminiz yok."}, status=403)
    if thread.thread_type == "group" and thread.only_admins_can_message and not membership.is_admin:
        return JsonResponse({"ok": False, "message": "Bu grupta yalnızca yöneticiler mesaj gönderebilir."}, status=403)

    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"ok": False, "message": "Mesaj boş olamaz."}, status=400)

    importance = (request.POST.get("importance") or "normal").strip()
    if importance not in {"normal", "important", "urgent"}:
        importance = "normal"

    linked_path = (request.POST.get("linked_path") or "").strip()[:500]
    linked_label = (request.POST.get("linked_label") or "").strip()[:180]
    if linked_path and (not linked_path.startswith("/") or linked_path.startswith("//")):
        linked_path = ""
        linked_label = ""

    message = ChatMessage.objects.create(
        thread=thread,
        sender=request.user,
        body=body,
        importance=importance,
        linked_path=linked_path,
        linked_label=linked_label,
    )
    ChatThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    ChatReadState.objects.update_or_create(
        thread=thread,
        user=request.user,
        defaults={"last_read_at": timezone.now()},
    )
    return JsonResponse({"ok": True, "message": _serialize_message(message, request.user)})


@login_required
@require_GET
def thread_messages(request, thread_id):
    thread = get_object_or_404(ChatThread, pk=thread_id)
    if not _membership_or_403(request.user, thread):
        return JsonResponse({"ok": False}, status=403)

    messages = list(
        thread.messages.select_related("sender").order_by("-created_at", "-id")[:150]
    )
    messages.reverse()
    ChatReadState.objects.update_or_create(
        thread=thread,
        user=request.user,
        defaults={"last_read_at": timezone.now()},
    )
    return JsonResponse({
        "ok": True,
        "messages": [_serialize_message(m, request.user) for m in messages],
    })


@login_required
@require_GET
def unread_count(request):
    memberships = ChatMembership.objects.filter(user=request.user).values_list("thread_id", flat=True)
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
