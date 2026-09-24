from app_settings.access import has_access
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import UserProfile
from .reminder_models import Reminder, ReminderState
from .reminder_service import pending_for_user, process_due_reminders


def is_manager(user):
    return has_access(user, "can_view_reports")


@login_required
@user_passes_test(is_manager)
def reminder_management(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        message = (request.POST.get("message") or "").strip()
        due_text = (request.POST.get("due_at") or "").strip()
        target_type = (request.POST.get("target_type") or "all").strip()
        repeat = (request.POST.get("repeat") or "none").strip()
        target_gorev = (request.POST.get("target_gorev") or "").strip()
        try:
            notify_interval_minutes = int(request.POST.get("notify_interval_minutes") or 15)
        except (TypeError, ValueError):
            notify_interval_minutes = 15
        if notify_interval_minutes not in {5, 10, 15, 30, 60, 120}:
            notify_interval_minutes = 15
        target_user = None

        if target_type == "user":
            user_id = request.POST.get("target_user")
            target_user = get_object_or_404(User, pk=user_id, is_active=True)
        elif target_type != "team":
            target_type = "all"
            target_gorev = ""

        try:
            naive = datetime.strptime(due_text, "%Y-%m-%dT%H:%M")
            due_at = timezone.make_aware(naive, timezone.get_current_timezone())
        except (TypeError, ValueError):
            messages.error(request, "Hatırlatma tarihi veya saati geçersiz.")
            return redirect("reminder_management")

        if not title:
            messages.error(request, "Hatırlatma başlığı boş bırakılamaz.")
            return redirect("reminder_management")

        Reminder.objects.create(
            title=title,
            message=message,
            due_at=due_at,
            target_type=target_type,
            target_user=target_user,
            target_gorev=target_gorev,
            repeat=repeat if repeat in {"none", "daily", "weekly", "monthly"} else "none",
            notify_interval_minutes=notify_interval_minutes,
            created_by=request.user,
        )
        messages.success(request, "Hatırlatma oluşturuldu.")
        return redirect("reminder_management")

    users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
    reminders = Reminder.objects.select_related("target_user", "created_by").order_by("-is_active", "-due_at")[:100]
    return render(
        request,
        "reminders/management.html",
        {
            "users": users,
            "reminders": reminders,
            "team_choices": UserProfile.GOREV_SECENEKLERI,
        },
    )


@login_required
@require_POST
def reminder_complete(request, reminder_id):
    reminder = get_object_or_404(Reminder, pk=reminder_id, is_active=True)
    if not reminder.applies_to(request.user):
        return redirect("order_list")

    state, _ = ReminderState.objects.get_or_create(reminder=reminder, user=request.user)
    state.last_completed_at = timezone.now()
    state.save(update_fields=["last_completed_at", "updated_at"])

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)


@login_required
@user_passes_test(is_manager)
@require_POST
def reminder_toggle(request, reminder_id):
    reminder = get_object_or_404(Reminder, pk=reminder_id)
    reminder.is_active = not reminder.is_active
    reminder.save(update_fields=["is_active"])
    messages.success(request, "Hatırlatma durumu güncellendi.")
    return redirect("reminder_management")


@login_required
@require_GET
def reminder_pending_api(request):
    rows = []
    for reminder, occurrence, state in pending_for_user(request.user):
        rows.append({
            "id": reminder.id,
            "title": reminder.title,
            "message": reminder.message,
            "occurrence": timezone.localtime(occurrence).strftime("%d.%m.%Y %H:%M"),
            "repeat": reminder.get_repeat_display(),
            "notify_interval_minutes": reminder.notify_interval_minutes,
        })
    return JsonResponse({"ok": True, "reminders": rows})


@login_required
def my_reminders(request):
    rows = [
        {"reminder": reminder, "occurrence": occurrence}
        for reminder, occurrence, state in pending_for_user(request.user)
    ]
    return render(request, "reminders/my_reminders.html", {"rows": rows})


@csrf_exempt
@require_POST
def reminder_tick(request):
    configured = getattr(settings, "REMINDER_CRON_TOKEN", "")
    supplied = request.headers.get("X-Reminder-Token", "")
    if not configured or supplied != configured:
        return HttpResponseForbidden("Forbidden")
    result = process_due_reminders()
    return JsonResponse({"ok": True, **result})
