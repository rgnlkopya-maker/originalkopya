from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Order
from .models import ShowroomDraft


class ShowroomFolio(models.Model):
    draft = models.OneToOneField(
        ShowroomDraft,
        on_delete=models.CASCADE,
        related_name="folio",
    )
    number = models.PositiveIntegerField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "product_cards"
        ordering = ["number"]

    def __str__(self):
        return f"Föy #{self.number}"


class ShowroomOrderLink(models.Model):
    draft = models.ForeignKey(
        ShowroomDraft,
        on_delete=models.CASCADE,
        related_name="order_links",
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="showroom_source",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "product_cards"
        ordering = ["id"]

    def __str__(self):
        return f"{self.order.siparis_numarasi} -> Föy #{self.draft.folio.number if hasattr(self.draft, 'folio') else self.draft_id}"


def ensure_showroom_folio(draft):
    existing = ShowroomFolio.objects.filter(draft=draft).first()
    if existing:
        return existing

    for _ in range(5):
        try:
            with transaction.atomic():
                last = (
                    ShowroomFolio.objects.select_for_update()
                    .order_by("-number")
                    .first()
                )
                next_number = (last.number if last else 0) + 1
                return ShowroomFolio.objects.create(draft=draft, number=next_number)
        except IntegrityError:
            continue

    return ShowroomFolio.objects.get(draft=draft)


@receiver(post_save, sender=ShowroomDraft)
def create_showroom_folio(sender, instance, created, **kwargs):
    if created:
        ensure_showroom_folio(instance)
