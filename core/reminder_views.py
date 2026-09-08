from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import UserProfile
from .reminder_models import Reminder, ReminderState


def is_manager(user):
    return user.is_staff or user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


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
