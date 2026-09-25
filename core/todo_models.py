from django.conf import settings
from django.db import models


class TodoItem(models.Model):
    ALARM_CHOICES = [
        (5, "5 dk"),
        (10, "10 dk"),
        (15, "15 dk"),
        (30, "30 dk"),
        (60, "1 saat"),
        (120, "2 saat"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_items")
    title = models.CharField(max_length=180)
    note = models.TextField(blank=True, default="")
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    alarm_enabled = models.BooleanField(default=False, db_index=True)
    alarm_interval_minutes = models.PositiveSmallIntegerField(default=15)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        ordering = ["completed_at", "due_at", "-created_at"]

    @property
    def is_completed(self):
        return self.completed_at is not None
