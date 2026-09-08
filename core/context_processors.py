# context_processors.py
from django.utils import timezone

from .models import Notification
from .reminder_models import Reminder, ReminderState


def _is_manager(user):
    return user.is_authenticated and (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=["patron", "mudur"]).exists()
    )


def notifications(request):
    due_reminders = []
    can_manage_reminders = False

    if request.user.is_authenticated:
        all_notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')
        unread_notification_count = all_notifications.filter(is_read=False).count()
        can_manage_reminders = _is_manager(request.user)

        now = timezone.now()
        states = {
            state.reminder_id: state
            for state in ReminderState.objects.filter(user=request.user).select_related("reminder")
        }
        for reminder in Reminder.objects.filter(is_active=True, due_at__lte=now).select_related("target_user", "created_by"):
            if not reminder.applies_to(request.user):
                continue
            occurrence = reminder.latest_due_before(now)
            if not occurrence:
                continue
            state = states.get(reminder.id)
            if state and state.last_completed_at and state.last_completed_at >= occurrence:
                continue
            due_reminders.append({"reminder": reminder, "occurrence": occurrence})
    else:
        all_notifications = Notification.objects.none()
        unread_notification_count = 0

    return {
        "all_notifications": all_notifications,
        "unread_notification_count": unread_notification_count,
        "due_reminders": due_reminders,
        "due_reminder_count": len(due_reminders),
        "can_manage_reminders": can_manage_reminders,
    }
