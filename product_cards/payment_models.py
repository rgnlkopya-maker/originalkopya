from django.db import models

from .models import ShowroomDraft


class ShowroomPayment(models.Model):
    ENTRY_CHOICES = [
        ("COLLECTION", "Tahsilat"),
        ("PROMISE", "Ödeme Sözü"),
    ]
    METHOD_CHOICES = [
        ("", "Belirtilmedi"),
        ("CASH", "Nakit"),
        ("CARD", "Kredi Kartı"),
        ("CHECK", "Çek"),
        ("NOTE", "Senet"),
    ]

    draft = models.ForeignKey(
        ShowroomDraft,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    entry_type = models.CharField(max_length=12, choices=ENTRY_CHOICES)
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, blank=True, default="")
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    payment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "payment_date", "id"]

    def __str__(self):
        return f"Föy #{self.draft_id} - {self.get_entry_type_display()} - {self.amount}"
