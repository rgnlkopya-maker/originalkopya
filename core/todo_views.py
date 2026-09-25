from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .todo_models import TodoItem


ALLOWED_INTERVALS = {5, 10, 15, 30, 60, 120}


@login_required
def todo_list(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        note = (request.POST.get("note") or "").strip()
        due_text = (request.POST.get("due_at") or "").strip()
        alarm_enabled = request.POST.get("alarm_enabled") == "on"
        try:
            interval = int(request.POST.get("alarm_interval_minutes") or 15)
        except ValueError:
            interval = 15
        if interval not in ALLOWED_INTERVALS:
            interval = 15
        due_at = None
        if due_text:
            try:
                due_at = timezone.make_aware(datetime.strptime(due_text, "%Y-%m-%dT%H:%M"), timezone.get_current_timezone())
            except ValueError:
                due_at = None
        if title:
            TodoItem.objects.create(
                user=request.user, title=title, note=note, due_at=due_at,
                alarm_enabled=bool(alarm_enabled and due_at),
                alarm_interval_minutes=interval,
            )
        return redirect("todo_list")

    now = timezone.now()
    items = list(TodoItem.objects.filter(user=request.user).order_by("completed_at", "due_at", "-created_at"))
    groups = {"overdue": [], "today": [], "upcoming": [], "no_date": [], "completed": []}
    today = timezone.localdate()
    for item in items:
        if item.completed_at:
            groups["completed"].append(item)
        elif not item.due_at:
            groups["no_date"].append(item)
        elif item.due_at < now:
            groups["overdue"].append(item)
        elif timezone.localtime(item.due_at).date() == today:
            groups["today"].append(item)
        else:
            groups["upcoming"].append(item)
    return render(request, "todos/list.html", {"groups": groups})


@login_required
@require_POST
def todo_complete(request, todo_id):
    item = get_object_or_404(TodoItem, pk=todo_id, user=request.user)
    item.completed_at = timezone.now()
    item.save(update_fields=["completed_at"])
    return redirect("todo_list")


@login_required
@require_POST
def todo_snooze(request, todo_id):
    item = get_object_or_404(TodoItem, pk=todo_id, user=request.user, completed_at__isnull=True)
    try:
        minutes = int(request.POST.get("minutes") or 10)
    except ValueError:
        minutes = 10
    if minutes not in {10, 30, 60}:
        minutes = 10
    item.snoozed_until = timezone.now() + timedelta(minutes=minutes)
    item.last_notified_at = None
    item.save(update_fields=["snoozed_until", "last_notified_at"])
    return redirect("todo_list")


@login_required
@require_POST
def todo_delete(request, todo_id):
    get_object_or_404(TodoItem, pk=todo_id, user=request.user).delete()
    return redirect("todo_list")
