from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import UserProfile
from .push_views import send_push_to_user
from .reminder_models import Reminder, ReminderState


User = get_user_model()


def reminder_target_users(reminder):
    qs = User.objects.filter(is_active=True)
    if reminder.target_type == "user":
        return qs.filter(pk=reminder.target_user_id)
    if reminder.target_type == "team":
        return qs.filter(userprofile__gorev=reminder.target_gorev)
    return qs


def pending_for_user(user, now=None):
    now = now or timezone.now()
    reminders = (
        Reminder.objects
        .filter(is_active=True, due_at__lte=now)
        .select_related("target_user", "created_by")
        .order_by("due_at", "id")
    )
    states = {
        state.reminder_id: state
        for state in ReminderState.objects.filter(user=user)
    }
    pending = []
    for reminder in reminders:
        if not reminder.applies_to(user):
            continue
        occurrence = reminder.latest_due_before(now)
        if not occurrence:
            continue
        state = states.get(reminder.id)
        if state and state.last_completed_at and state.last_completed_at >= occurrence:
            continue
        pending.append((reminder, occurrence, state))
    return pending


def process_due_reminders(now=None):
    now = now or timezone.now()
    reminders = (
        Reminder.objects
        .filter(is_active=True, due_at__lte=now)
        .select_related("target_user", "created_by")
        .order_by("due_at", "id")
    )

    checked = 0
    notified = 0
    delivered = 0

    for reminder in reminders:
        occurrence = reminder.latest_due_before(now)
        if not occurrence:
            continue

        interval = max(5, int(reminder.notify_interval_minutes or 15))
        for user in reminder_target_users(reminder).iterator():
            checked += 1
            with transaction.atomic():
                state, _ = ReminderState.objects.select_for_update().get_or_create(
                    reminder=reminder,
                    user=user,
                )
                if state.last_completed_at and state.last_completed_at >= occurrence:
                    continue
                if (
                    state.last_notified_at
                    and state.last_notified_at >= occurrence
                    and now - state.last_notified_at < timedelta(minutes=interval)
                ):
                    continue

                # Aynı cron aynı anda iki kez çalışsa bile tekrar push atılmasını engeller.
                state.last_notified_at = now
                state.save(update_fields=["last_notified_at", "updated_at"])

            notified += 1
            body = (reminder.message or "").strip() or reminder.title
            delivered += send_push_to_user(
                user=user,
                title=f"Hatırlatma: {reminder.title}",
                body=body,
                url="/hatirlatmalarim/",
                tag=f"moli-reminder-{reminder.id}-{user.id}",
            )

    return {
        "checked": checked,
        "notified": notified,
        "delivered": delivered,
    }
