from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import ProductCard


def _can_manage(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


@login_required
@require_POST
def toggle_product_card_status(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")

    card = get_object_or_404(ProductCard.objects.select_related("urun"), pk=request.POST.get("card_id"))
    card.urun.aktif = not card.urun.aktif
    card.urun.save(update_fields=["aktif"])

    if card.urun.aktif:
        messages.success(request, f"{card.urun.kod} tekrar aktif edildi.")
    else:
        messages.success(request, f"{card.urun.kod} pasife alındı. Geçmiş siparişler etkilenmedi.")

    return redirect("product_card_list")
