from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from app_settings.access import has_access
from core.models import Order, OrderEvent
from core.services.order_status import sync_order_stage_from_events


PRODUCTION_STAGES = {
    "malzeme_durum",
    "kesim_durum",
    "dikim_durum",
    "dikim_fason_durumu",
    "nakis_durumu",
    "susleme_durum",
    "susleme_fason_durumu",
    "hazir_durum",
}


def _term_filter(term):
    return (
        Q(siparis_numarasi__icontains=term)
        | Q(musteri__ad__icontains=term)
        | Q(musteri_referans__icontains=term)
        | Q(urun_kodu__icontains=term)
        | Q(renk__icontains=term)
        | Q(beden__icontains=term)
    )


@login_required
@require_GET
def search_transfer_targets(request, source_order_id):
    if not has_access(request.user, "can_edit_orders"):
        return JsonResponse({"results": []}, status=403)

    source = get_object_or_404(Order, pk=source_order_id)
    raw_q = (request.GET.get("q") or "").strip()
    terms = [part for part in raw_q.split() if part]
    if not terms:
        return JsonResponse({"results": []})

    orders = (
        Order.objects.filter(is_active=True)
        .exclude(pk=source.pk)
        .select_related("musteri")
    )
    for term in terms:
        orders = orders.filter(_term_filter(term))

    orders = orders.order_by("-id")[:20]

    results = []
    for order in orders:
        results.append({
            "id": order.pk,
            "siparis_numarasi": order.siparis_numarasi,
            "musteri": order.musteri.ad if order.musteri else "Stoğa Üretim",
            "musteri_referans": order.musteri_referans or "",
            "urun_kodu": order.urun_kodu or "",
            "renk": order.renk or "",
            "beden": order.beden or "",
        })
    return JsonResponse({"results": results})


@login_required
@require_POST
def transfer_production_history(request, source_order_id):
    if not has_access(request.user, "can_edit_orders"):
        return JsonResponse({"ok": False, "error": "Bu işlem için yetkiniz yok."}, status=403)

    source = get_object_or_404(Order, pk=source_order_id)
    target_id = (request.POST.get("target_order_id") or "").strip()
    target_number = (request.POST.get("target_order_number") or "").strip()

    target = None
    if target_id.isdigit():
        target = Order.objects.filter(pk=int(target_id)).first()
    elif target_number:
        target = Order.objects.filter(siparis_numarasi__iexact=target_number).first()

    if not target:
        return JsonResponse({"ok": False, "error": "Aktarılacak hedef siparişi seçin."}, status=400)
    if target.pk == source.pk:
        return JsonResponse({"ok": False, "error": "Aynı siparişe aktarım yapılamaz."}, status=400)
    if not target.is_active:
        return JsonResponse({"ok": False, "error": "Hedef sipariş pasif durumda."}, status=400)

    source_events = list(
        OrderEvent.objects.filter(order=source, event_type="stage", stage__in=PRODUCTION_STAGES)
        .order_by("timestamp", "id")
    )
    if not source_events:
        return JsonResponse({"ok": False, "error": "Bu siparişte aktarılacak üretim geçmişi yok."}, status=400)

    existing = set(
        OrderEvent.objects.filter(order=target, event_type="stage", stage__in=PRODUCTION_STAGES)
        .values_list("stage", "value", "user", "timestamp")
    )

    created_count = 0
    affected_stages = set()
    actor = request.user.get_full_name().strip() or request.user.username

    with transaction.atomic():
        for event in source_events:
            signature = (event.stage, event.value, event.user, event.timestamp)
            if signature in existing:
                continue
            OrderEvent.objects.create(
                order=target,
                user=event.user,
                gorev=event.gorev,
                stage=event.stage,
                value=event.value,
                adet=event.adet,
                parca=event.parca,
                aciklama=None,
                ortak_calisanlar=event.ortak_calisanlar,
                fasoncu=event.fasoncu,
                nakisci=event.nakisci,
                timestamp=event.timestamp,
                event_type="stage",
            )
            created_count += 1
            affected_stages.add(event.stage)

        for stage in affected_stages:
            sync_order_stage_from_events(target, stage)

        OrderEvent.objects.create(
            order=source,
            user=actor,
            gorev="yok",
            stage="Üretim Aktarımı",
            value=f"{target.siparis_numarasi} siparişine aktarıldı",
            adet=0,
            event_type="stage",
        )
        OrderEvent.objects.create(
            order=target,
            user=actor,
            gorev="yok",
            stage="Üretim Aktarımı",
            value=f"{source.siparis_numarasi} siparişinden alındı",
            adet=0,
            event_type="stage",
        )

    return JsonResponse({
        "ok": True,
        "count": created_count,
        "target_order_id": target.pk,
        "target_order_number": target.siparis_numarasi,
    })
