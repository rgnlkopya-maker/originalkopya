from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ConsignmentMovement, ConsignmentStock, Musteri, Order, OrderEvent


def _can_manage(user):
    if user.is_superuser:
        return True
    access = getattr(user, "access", None)
    return bool(access and (access.can_view_depots or access.can_edit_orders or access.can_manage_planning))


@login_required
def consignment_list(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    stocks = ConsignmentStock.objects.select_related("customer", "source_order").filter(quantity_remaining__gt=0)
    customer_id = request.GET.get("musteri")
    if customer_id:
        stocks = stocks.filter(customer_id=customer_id)
    movements = ConsignmentMovement.objects.select_related("stock__customer", "target_order", "user")[:100]
    return render(request, "core/consignment_list.html", {
        "stocks": stocks,
        "customers": Musteri.objects.filter(aktif=True).order_by("ad"),
        "movements": movements,
        "selected_customer": str(customer_id or ""),
        "total_remaining": stocks.aggregate(v=Sum("quantity_remaining"))["v"] or 0,
    })


@login_required
@require_POST
def consignment_add(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    order_number = (request.POST.get("source_order") or "").strip()
    customer_id = request.POST.get("customer_id")
    try:
        quantity = max(1, int(request.POST.get("quantity") or 1))
    except ValueError:
        quantity = 1
    source = Order.objects.select_related("musteri").filter(siparis_numarasi__iexact=order_number).first()
    customer = Musteri.objects.filter(pk=customer_id, aktif=True).first()
    if not source or not customer:
        messages.error(request, "Sipariş veya müşteri bulunamadı.")
        return redirect("consignment_list")
    if quantity > (source.adet or 1):
        messages.error(request, "Konsinye adedi kaynak sipariş adedinden büyük olamaz.")
        return redirect("consignment_list")
    with transaction.atomic():
        stock = ConsignmentStock.objects.create(
            customer=customer, source_order=source, urun_kodu=source.urun_kodu or "",
            renk=source.renk, beden=source.beden, quantity_sent=quantity,
            quantity_remaining=quantity, cost_snapshot=source.efektif_maliyet,
            cost_currency=source.maliyet_para_birimi or "TRY", created_by=request.user,
            note=(request.POST.get("note") or "").strip(),
        )
        ConsignmentMovement.objects.create(stock=stock, movement_type="IN", quantity=quantity, user=request.user, note="Konsinye müşteriye gönderildi.")
    messages.success(request, f"{source.siparis_numarasi} konsinye stoğuna eklendi.")
    return redirect("consignment_list")


@login_required
@require_POST
def consignment_use(request, order_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    target = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    stock_id = request.POST.get("stock_id")
    try:
        quantity = max(1, int(request.POST.get("quantity") or 1))
    except ValueError:
        quantity = 1
    if not target.musteri_id:
        messages.error(request, "Siparişte müşteri bulunmuyor.")
        return redirect("order_detail", pk=target.pk)
    with transaction.atomic():
        stock = get_object_or_404(ConsignmentStock.objects.select_for_update().select_related("source_order"), pk=stock_id)
        same = (
            stock.customer_id == target.musteri_id and
            (stock.urun_kodu or "").strip().casefold() == (target.urun_kodu or "").strip().casefold() and
            (stock.renk or "").strip().casefold() == (target.renk or "").strip().casefold() and
            (stock.beden or "").strip().casefold() == (target.beden or "").strip().casefold()
        )
        if not same:
            messages.error(request, "Seçilen konsinye ürün müşteri / ürün / renk / beden ile eşleşmiyor.")
            return redirect("order_detail", pk=target.pk)
        already = ConsignmentMovement.objects.filter(target_order=target, movement_type="USE").aggregate(v=Sum("quantity"))["v"] or 0
        max_needed = max(0, (target.adet or 1) - already)
        if quantity > stock.quantity_remaining or quantity > max_needed:
            messages.error(request, "Seçilen adet mevcut konsinye stoğunu veya sipariş ihtiyacını aşıyor.")
            return redirect("order_detail", pk=target.pk)

        source_events = OrderEvent.objects.filter(order=stock.source_order, event_type="stage").exclude(stage="sevkiyat_durum").order_by("timestamp", "id")
        for ev in source_events:
            OrderEvent.objects.create(
                order=target, user=ev.user, gorev=ev.gorev, stage=ev.stage, value=ev.value,
                adet=min(ev.adet or 1, quantity), parca=ev.parca,
                aciklama=((ev.aciklama or "") + f" [Konsinye kaynağı: {stock.source_order.siparis_numarasi}]").strip(),
                ortak_calisanlar=ev.ortak_calisanlar, fasoncu=ev.fasoncu, nakisci=ev.nakisci,
                timestamp=ev.timestamp, event_type="stage",
            )
        stock.quantity_remaining -= quantity
        stock.save(update_fields=["quantity_remaining"])
        ConsignmentMovement.objects.create(
            stock=stock, movement_type="USE", quantity=quantity, target_order=target, user=request.user,
            note=f"{target.siparis_numarasi} siparişinde kullanıldı."
        )
        OrderEvent.objects.create(
            order=target, user=request.user.username, gorev="yok", stage="konsinye",
            value="konsinye_stoktan_karsilandi", adet=quantity,
            aciklama=f"{stock.source_order.siparis_numarasi} kaynaklı konsinye stoktan {quantity} adet kullanıldı."
        )
    messages.success(request, f"{quantity} adet konsinye stoktan düşüldü; üretim geçmişi siparişe aktarıldı.")
    return redirect("order_detail", pk=target.pk)


@login_required
@require_POST
def consignment_send_order(request, order_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    source = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    if source.siparis_tipi != "KONSINYE":
        messages.error(request, "Bu işlem yalnızca KONSİNYE tipindeki üretimlerde kullanılabilir.")
        return redirect("order_detail", pk=source.pk)
    if not source.musteri_id:
        messages.error(request, "Konsinye üretimde müşteri seçilmelidir.")
        return redirect("order_detail", pk=source.pk)
    if source.hazir_durum != "bitti":
        messages.error(request, "Ürün Hazır aşaması tamamlanmadan konsinyeye gönderilemez.")
        return redirect("order_detail", pk=source.pk)
    try:
        quantity = max(1, int(request.POST.get("quantity") or 1))
    except ValueError:
        quantity = 1
    already_sent = ConsignmentStock.objects.filter(source_order=source).aggregate(v=Sum("quantity_sent"))["v"] or 0
    unsent = max(0, (source.adet or 1) - already_sent)
    if quantity > unsent:
        messages.error(request, f"Gönderilebilecek konsinye adedi {unsent}.")
        return redirect("order_detail", pk=source.pk)
    with transaction.atomic():
        stock = ConsignmentStock.objects.create(
            customer=source.musteri,
            source_order=source,
            urun_kodu=source.urun_kodu or "",
            renk=source.renk,
            beden=source.beden,
            quantity_sent=quantity,
            quantity_remaining=quantity,
            cost_snapshot=source.efektif_maliyet,
            cost_currency=source.maliyet_para_birimi or "TRY",
            created_by=request.user,
            note=(request.POST.get("note") or "").strip(),
        )
        ConsignmentMovement.objects.create(
            stock=stock,
            movement_type="IN",
            quantity=quantity,
            user=request.user,
            note="KONSİNYE üretim siparişinden müşteriye gönderildi.",
        )
        OrderEvent.objects.create(
            order=source,
            user=request.user.username,
            gorev="yok",
            stage="konsinye",
            value="konsinyeye_gonderildi",
            adet=quantity,
            aciklama=f"{source.musteri} konsinye stoğuna {quantity} adet gönderildi.",
        )
    messages.success(request, f"{quantity} adet ürün {source.musteri} konsinye stoğuna gönderildi.")
    return redirect("order_detail", pk=source.pk)
