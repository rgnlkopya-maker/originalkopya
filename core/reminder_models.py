from calendar import monthrange
from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Reminder(models.Model):
    TARGET_CHOICES = [
        ("all", "Herkes"),
        ("team", "Ekip / Görev"),
        ("user", "Belirli Personel"),
    ]
    REPEAT_CHOICES = [
        ("none", "Tek Sefer"),
        ("daily", "Her Gün"),
        ("weekly", "Her Hafta"),
        ("monthly", "Her Ay"),
    ]

    title = models.CharField(max_length=160)
    message = models.TextField(blank=True, default="")
    due_at = models.DateTimeField(db_index=True)
    target_type = models.CharField(max_length=10, choices=TARGET_CHOICES, default="all", db_index=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="targeted_reminders",
    )
    target_gorev = models.CharField(max_length=30, blank=True, default="")
    repeat = models.CharField(max_length=10, choices=REPEAT_CHOICES, default="none")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reminders",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        ordering = ["-due_at", "-id"]

    def __str__(self):
        return self.title

    def applies_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if self.target_type == "all":
            return True
        if self.target_type == "user":
            return self.target_user_id == user.id
        if self.target_type == "team":
            profile = getattr(user, "userprofile", None)
            return bool(profile and profile.gorev == self.target_gorev)
        return False

    def latest_due_before(self, now=None):
        now = now or timezone.now()
        if self.due_at > now:
            return None
        if self.repeat == "none":
            return self.due_at

        local_now = timezone.localtime(now)
        local_base = timezone.localtime(self.due_at)
        tz = timezone.get_current_timezone()

        if self.repeat == "daily":
            candidate = timezone.make_aware(
                datetime.combine(local_now.date(), local_base.time().replace(tzinfo=None)), tz
            )
            if candidate > now:
                candidate -= timedelta(days=1)
            return max(candidate, self.due_at)

        if self.repeat == "weekly":
            days_back = (local_now.weekday() - local_base.weekday()) % 7
            day = local_now.date() - timedelta(days=days_back)
            candidate = timezone.make_aware(
                datetime.combine(day, local_base.time().replace(tzinfo=None)), tz
            )
            if candidate > now:
                candidate -= timedelta(days=7)
            return max(candidate, self.due_at)

        if self.repeat == "monthly":
            year, month = local_now.year, local_now.month
            day = min(local_base.day, monthrange(year, month)[1])
            candidate = timezone.make_aware(
                datetime.combine(local_now.date().replace(day=day), local_base.time().replace(tzinfo=None)), tz
            )
            if candidate > now:
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
                day = min(local_base.day, monthrange(year, month)[1])
                candidate = timezone.make_aware(
                    datetime.combine(datetime(year, month, day).date(), local_base.time().replace(tzinfo=None)), tz
                )
            return max(candidate, self.due_at)

        return self.due_at


class ReminderState(models.Model):
    reminder = models.ForeignKey(Reminder, on_delete=models.CASCADE, related_name="states")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder_states")
    last_completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "core"
        constraints = [
            models.UniqueConstraint(fields=["reminder", "user"], name="unique_reminder_state_user")
        ]

    def __str__(self):
        return f"{self.user} - {self.reminder}"
