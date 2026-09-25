from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .push_views import send_push_to_user
from .todo_models import TodoItem


def process_due_todos(now=None):
    now = now or timezone.now()
    items = TodoItem.objects.filter(
        completed_at__isnull=True,
        alarm_enabled=True,
        due_at__isnull=False,
        due_at__lte=now,
    ).select_related("user")
    notified = delivered = 0
    for item in items:
        if item.snoozed_until and item.snoozed_until > now:
            continue
        interval = max(5, int(item.alarm_interval_minutes or 15))
        with transaction.atomic():
            locked = TodoItem.objects.select_for_update().get(pk=item.pk)
            if locked.completed_at or not locked.alarm_enabled:
                continue
            if locked.snoozed_until and locked.snoozed_until > now:
                continue
            if locked.last_notified_at and now - locked.last_notified_at < timedelta(minutes=interval):
                continue
            locked.last_notified_at = now
            locked.save(update_fields=["last_notified_at"])
        notified += 1
        delivered += send_push_to_user(
            user=item.user,
            title=f"Yapılacak: {item.title}",
            body=(item.note or "").strip() or "Tamamlanmayı bekleyen işiniz var.",
            url="/yapilacaklar/",
            tag=f"moli-todo-{item.id}",
        )
    return {"notified": notified, "delivered": delivered}
