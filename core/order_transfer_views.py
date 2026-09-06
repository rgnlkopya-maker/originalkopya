from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

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


def _norm(value):
    return (value or "").strip().casefold()


@login_required
@require_POST
def transfer_production_history(request, source_order_id):
    if not has_access(request.user, "can_edit_orders"):
        return JsonResponse({"ok": False, "error": "Bu işlem için yetkiniz yok."}, status=403)

    source = get_object_or_404(Order, pk=source_order_id)
    target_number = (request.POST.get("target_order_number") or "").strip()
    if not target_number:
        return JsonResponse({"ok": False, "error": "Yeni sipariş numarasını yazın."}, status=400)

    target = Order.objects.filter(siparis_numarasi__iexact=target_number).first()
    if not target:
        return JsonResponse({"ok": False, "error": "Bu sipariş numarası bulunamadı."}, status=404)
    if target.pk == source.pk:
        return JsonResponse({"ok": False, "error": "Aynı siparişe aktarım yapılamaz."}, status=400)
    if not target.is_active:
        return JsonResponse({"ok": False, "error": "Hedef sipariş pasif durumda."}, status=400)

    if _norm(source.urun_kodu) != _norm(target.urun_kodu):
        return JsonResponse({"ok": False, "error": "Ürün kodları eşleşmiyor. Yanlış ürüne aktarımı önlemek için işlem durduruldu."}, status=400)

    if source.renk and target.renk and _norm(source.renk) != _norm(target.renk):
        return JsonResponse({"ok": False, "error": "Renkler eşleşmiyor. Hedef siparişi kontrol edin."}, status=400)
    if source.beden and target.beden and _norm(source.beden) != _norm(target.beden):
        return JsonResponse({"ok": False, "error": "Bedenler eşleşmiyor. Hedef siparişi kontrol edin."}, status=400)

    source_events = list(
        OrderEvent.objects.filter(
            order=source,
            event_type="stage",
            stage__in=PRODUCTION_STAGES,
        ).order_by("timestamp", "id")
    )
    if not source_events:
        return JsonResponse({"ok": False, "error": "Bu siparişte aktarılacak üretim geçmişi yok."}, status=400)

    existing = set(
        OrderEvent.objects.filter(order=target, event_type="stage", stage__in=PRODUCTION_STAGES)
        .values_list("stage", "value", "user", "timestamp")
    )

    created_count = 0
    affected_stages = set()
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

    return JsonResponse({
        "ok": True,
        "count": created_count,
        "target_order_id": target.pk,
        "target_order_number": target.siparis_numarasi,
    })
