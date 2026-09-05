from django.conf import settings
from django.db import models


class PlanningEntry(models.Model):
    SECTION_CHOICES = [
        ("kesim", "Kesim Planlaması"),
        ("dikim", "Dikim Planlaması"),
        ("susleme", "Süsleme Planlaması"),
    ]

    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    date = models.DateField()
    note = models.TextField(blank=True, default="")
    text_color = models.CharField(max_length=7, default="#182033")
    background_color = models.CharField(max_length=7, default="#ffffff")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["section", "date"], name="unique_planning_section_date")]
        ordering = ["date", "section"]

    def __str__(self):
        return f"{self.get_section_display()} - {self.date}"
