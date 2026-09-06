from django.conf import settings
from django.db import models


class PlanningEntry(models.Model):
    SECTION_CHOICES = [
        ("kesim", "Kesim Planlaması"),
        ("dikim", "Dikim Planlaması"),
        ("susleme", "Süsleme Planlaması"),
        ("sevkiyat", "Sevkiyat Planlaması"),
    ]

    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    date = models.DateField()
    note = models.TextField(blank=True, default="")
    text_color = models.CharField(max_length=7, default="#182033")
    background_color = models.CharField(max_length=7, default="#ffffff")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "section", "id"]

    def __str__(self):
        return f"{self.get_section_display()} - {self.date}"


class ShipmentPlan(models.Model):
    order = models.OneToOneField(
        "core.Order",
        on_delete=models.CASCADE,
        related_name="shipment_plan",
    )
    planned_date = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_shipment_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["planned_date", "order__siparis_numarasi"]

    def __str__(self):
        return f"{self.order.siparis_numarasi} - {self.planned_date}"
