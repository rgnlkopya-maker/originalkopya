import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Beden, CustomerPricingRule, Musteri, Order, Renk, URUN_TIPI_CHOICES, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraft, ShowroomDraftItem
from .payment_models import ShowroomPayment
from .price_list_views import _can_manage, _ensure_price_rates, _price_rows, _real_profit_rate
from .drive_folio_backup import queue_folio_drive_sync


CUSTOMER_BASE_PRICE_SIZE = "BAZ FİYAT (BEDENSİZ)"


def _normalize_pricing_operations(raw):
    ops=[]
    if not isinstance(raw,list):
        return ops
    for item in raw:
        if not isinstance(item,dict):
            continue
        op_type=str(item.get("type") or "").upper()
        mode=str(item.get("mode") or "").upper()
        value=max(Decimal("0"),_decimal(item.get("value"),"0"))
        if op_type=="DISCOUNT":
            if mode not in {"PERCENT","AMOUNT"}: mode="AMOUNT"
            if mode=="PERCENT": value=min(Decimal("100"),value)
        elif op_type=="VAT":
            mode="PERCENT"; value=min(Decimal("100"),value)
        else:
            continue
        ops.append({"type":op_type,"mode":mode,"value":str(value)})
    return ops


def _apply_pricing_operations(subtotal, operations, target=None):
    current=max(Decimal("0"),Decimal(subtotal or 0))
    steps=[]
    for op in _normalize_pricing_operations(operations):
        value=Decimal(op["value"])
        before=current
        if op["type"]=="DISCOUNT":
            change=(current*value/Decimal("100")) if op["mode"]=="PERCENT" else value
            change=min(current,max(Decimal("0"),change)); current-=change
            signed=-change
        else:
            change=current*value/Decimal("100"); current+=change; signed=change
        steps.append({**op,"before":before,"change":signed,"after":current})
    operations_total=current
    adjustment=Decimal("0")
    if target is not None:
        target=max(Decimal("0"),Decimal(target)); adjustment=target-current; current=target
    return {"operations_total":operations_total,"adjustment":adjustment,"folio_total":current,"steps":steps}


def _pricing_customer_ids():
    return list(
        CustomerPricingRule.objects.filter(active=True).values_list("customer_id", flat=True)
    )


def _validate_customer_base_price_rows(customer, raw_items):
    has_pricing_rule = bool(
        customer
        and CustomerPricingRule.objects.filter(customer=customer, active=True).exists()
    )
    for item in raw_items:
        for row in item.get("satirlar") or []:
            sizes = row.get("bedenler") or []
            if CUSTOMER_BASE_PRICE_SIZE not in sizes:
                continue
            if not has_pricing_rule:
                return "Baz fiyat (bedensiz) yalnızca özel fiyat kuralı bulunan müşterilerde kullanılabilir."
            if len(sizes) != 1:
                return "Baz fiyat (bedensiz) ile gerçek beden aynı satırda seçilemez."
    return None


def _active_draft(user):
    return ShowroomDraft.objects.filter(created_by=user, status="DRAFT").order_by("-updated_at", "-id").first()


def _lock_showroom_user(user):
    user.__class__.objects.select_for_update().get(pk=user.pk)


def _decimal(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _create_draft(user, customer=None):
    settings = PriceListSettings.get_solo()
    return ShowroomDraft.objects.create(created_by=user, customer=customer, status="DRAFT", currency="TRY", profit_rate=settings.profit_rate, discount_rate=Decimal("0"), monthly_term_rate=settings.monthly_term_rate, usd_try=settings.usd_try, eur_try=settings.eur_try, overall_discount_amount=Decimal("0"), vat_rate=Decimal("0"))


def _payment_data(draft):
    if not draft: return []
    return [{"entry_type":p.entry_type,"method":p.method,"amount":str(p.amount),"payment_date":p.payment_date.isoformat() if p.payment_date else "","due_date":p.due_date.isoformat() if p.due_date else "","note":p.note} for p in draft.payments.all().order_by("due_date","payment_date","id")]


def _serialize_draft(draft):
    if not draft:
        return {"ok": True, "draft": None, "customer_id": "", "order_taken_by": "", "order_type": "SERI", "items": [], "payments": [], "pricing_operations": [], "folio_adjustment_target": "", "discount_rate": "0", "discount_amount": "0", "vat_rate": "0", "previous_balance": "0"}
    groups=[]; group_map={}; row_maps={}
    for db_item in draft.items.select_related("product_card__urun").order_by("created_at", "id"):
        code=db_item.product_card.urun.kod; unit_price=str(db_item.unit_price); group_key=(db_item.product_card_id,unit_price)
        if group_key not in group_map:
            group_map[group_key]=len(groups); groups.append({"urun_kodu":code,"anlasilan_fiyat":unit_price,"satirlar":[]}); row_maps[group_key]={}
        group=groups[group_map[group_key]]; row_key=(db_item.color,db_item.quantity,db_item.description)
        if row_key not in row_maps[group_key]:
            row_maps[group_key][row_key]=len(group["satirlar"]); group["satirlar"].append({"renk":db_item.color,"bedenler":[],"adet":db_item.quantity,"aciklama":db_item.description})
        group["satirlar"][row_maps[group_key][row_key]]["bedenler"].append(db_item.size)
    return {"ok":True,"draft":draft.id,"customer_id":str(draft.customer_id or ""),"order_taken_by":draft.order_taken_by or "","order_type":draft.order_type or "SERI","items":groups,"payments":_payment_data(draft),"pricing_operations":draft.pricing_operations or [],"folio_adjustment_target":str(draft.folio_adjustment_target) if draft.folio_adjustment_target is not None else "","discount_rate":str(draft.discount_rate or 0),"discount_amount":str(draft.overall_discount_amount or 0),"vat_rate":str(draft.vat_rate or 0),"previous_balance":str(draft.previous_balance or 0),"updated_at":draft.updated_at.isoformat() if draft.updated_at else None}


def _draft_summary(draft):
    line_total=ExpressionWrapper(F("quantity")*F("unit_price"),output_field=DecimalField(max_digits=20,decimal_places=2))
    items=draft.items.aggregate(product_count=Count("product_card",distinct=True),total_qty=Sum("quantity"),subtotal=Sum(line_total)); subtotal=items["subtotal"] or Decimal("0")
    pricing_ops=draft.pricing_operations or []
    pricing_steps=[]
    if pricing_ops:
        pricing=_apply_pricing_operations(subtotal,pricing_ops,draft.folio_adjustment_target)
        discount=sum((-step["change"] for step in pricing["steps"] if step["change"]<0),Decimal("0"))
        vat=sum((step["change"] for step in pricing["steps"] if step["type"]=="VAT"),Decimal("0"))
        vat_rate=Decimal("0"); folio_total=pricing["folio_total"]
        for step in pricing["steps"]:
            pricing_steps.append({
                "type": step["type"],
                "mode": step["mode"],
                "value": str(Decimal(str(step["value"])).quantize(Decimal("0.01"))),
                "change": str(Decimal(step["change"]).quantize(Decimal("0.01"))),
                "after": str(Decimal(step["after"]).quantize(Decimal("0.01"))),
            })
    else:
        discount=subtotal*draft.discount_rate/Decimal("100") if draft.discount_rate and draft.discount_rate>0 else draft.overall_discount_amount or Decimal("0")
        discount=min(subtotal,max(Decimal("0"),discount)); taxable=max(Decimal("0"),subtotal-discount); vat_rate=max(Decimal("0"),min(Decimal("100"),draft.vat_rate or Decimal("0"))); vat=taxable*vat_rate/Decimal("100"); folio_total=taxable+vat
    folio_adjustment = Decimal("0")
    folio_adjustment_applied = draft.folio_adjustment_target is not None
    if pricing_ops and folio_adjustment_applied:
        folio_adjustment = pricing["adjustment"]
    previous_balance=max(Decimal("0"),draft.previous_balance or Decimal("0")); total=folio_total+previous_balance
    collected=draft.payments.filter(entry_type="COLLECTION").aggregate(v=Sum("amount"))["v"] or Decimal("0"); promised=draft.payments.filter(entry_type="PROMISE").aggregate(v=Sum("amount"))["v"] or Decimal("0"); remaining=max(Decimal("0"),total-collected)
    return {"id":draft.id,"customer":draft.customer.ad if draft.customer else "Müşteri seçilmedi","product_count":items["product_count"] or 0,"total_qty":items["total_qty"] or 0,"subtotal":str(subtotal.quantize(Decimal("0.01"))),"discount":str(discount.quantize(Decimal("0.01"))),"vat_rate":str(vat_rate.quantize(Decimal("0.01"))),"vat":str(vat.quantize(Decimal("0.01"))),"pricing_steps":pricing_steps,"folio_adjustment":str(folio_adjustment.quantize(Decimal("0.01"))),"folio_adjustment_applied":folio_adjustment_applied,"folio_total":str(folio_total.quantize(Decimal("0.01"))),"previous_balance":str(previous_balance.quantize(Decimal("0.01"))),"total":str(total.quantize(Decimal("0.01"))),"collected":str(collected.quantize(Decimal("0.01"))),"promised":str(promised.quantize(Decimal("0.01"))),"remaining":str(remaining.quantize(Decimal("0.01"))),"updated_at":timezone.localtime(draft.updated_at).strftime("%d.%m.%Y %H:%M"),"status":draft.status}


def _effective_price_factor(draft):
    """Föydeki fiyat işlemlerini ürün birim fiyatlarına oransal olarak yansıtır."""
    subtotal = sum(
        (Decimal(item.unit_price or 0) * Decimal(max(1, int(item.quantity or 1))) for item in draft.items.all()),
        Decimal("0"),
    )
    if subtotal <= 0:
        return Decimal("0")

    if draft.pricing_operations or draft.folio_adjustment_target is not None:
        result = _apply_pricing_operations(subtotal, draft.pricing_operations or [], draft.folio_adjustment_target)
        return result["folio_total"] / subtotal

    discount = (
        subtotal * Decimal(draft.discount_rate or 0) / Decimal("100")
        if draft.discount_rate and draft.discount_rate > 0
        else Decimal(draft.overall_discount_amount or 0)
    )
    discount = min(subtotal, max(Decimal("0"), discount))
    taxable = max(Decimal("0"), subtotal - discount)
    vat_rate = max(Decimal("0"), min(Decimal("100"), Decimal(draft.vat_rate or 0)))
    folio_total = taxable + (taxable * vat_rate / Decimal("100"))
    return folio_total / subtotal


def _effective_serialized_items(draft):
    data = _serialize_draft(draft)
    factor = _effective_price_factor(draft)
    for item in data["items"]:
        base_price = _decimal(item.get("anlasilan_fiyat"), "0")
        item["anlasilan_fiyat"] = str((base_price * factor).quantize(Decimal("0.01")))
    return data["items"]


def _payment_rows(draft): return list(draft.payments.all().order_by("due_date","payment_date","id"))


def _customer_folios(user, customer):
    return (
        ShowroomDraft.objects.filter(
            created_by=user,
            customer=customer,
            status__in=["PENDING", "APPROVED", "TRANSFERRED"],
        )
        .select_related("customer")
        .prefetch_related("items__product_card__urun", "payments")
        .order_by("-updated_at", "-id")
    )

def _build_payment_rows(draft, raw_payments):
    rows=[]
    if not isinstance(raw_payments,list): return rows
    for p in raw_payments:
        entry_type=str(p.get("entry_type") or "").upper()
        if entry_type not in {"COLLECTION","PROMISE"}: continue
        value=max(Decimal("0"),_decimal(p.get("amount"),"0"))
        if value<=0: continue
        method=str(p.get("method") or "").upper()
        if method not in {"CASH","CARD","CHECK","NOTE"}: method=""
        rows.append(ShowroomPayment(draft=draft,entry_type=entry_type,method=method,amount=value,payment_date=p.get("payment_date") or None,due_date=p.get("due_date") or None,note=str(p.get("note") or "")[:300]))
    return rows


def _delete_draft_safely(draft):
    ShowroomPayment.objects.filter(draft=draft).delete()
    ShowroomDraftItem.objects.filter(draft=draft).delete()
    ShowroomDraft.objects.filter(pk=draft.pk).delete()

def _showroom_page_context(request):
    settings=PriceListSettings.get_solo()
    if settings.profit_rate<=0 and settings.discount_rate>0: settings.discount_rate=Decimal("0"); settings.save(update_fields=["discount_rate","updated_at"])
    rate_error=_ensure_price_rates(settings); show_inactive=request.GET.get("durum")=="pasif"; musteriler=Musteri.objects.filter(aktif=True).order_by("ad"); renkler=Renk.objects.filter(aktif=True).order_by("ad"); bedenler=Beden.objects.filter(aktif=True).order_by("ad"); urun_kodlari=UrunKod.objects.filter(aktif=True).order_by("kod")
    return {"settings":settings,"rows":_price_rows(settings,active=not show_inactive),"show_inactive":show_inactive,"inactive_count":ProductCard.objects.filter(price_list_active=False).count(),"rate_error":rate_error,"real_profit_rate":_real_profit_rate(settings.profit_rate,settings.discount_rate),"showroom_mode":True,"musteriler":musteriler,"renkler":renkler,"bedenler":bedenler,"urun_kodlari":urun_kodlari,"aktif_musteriler":musteriler,"aktif_renkler":renkler,"aktif_bedenler":bedenler,"aktif_urun_kodlari":urun_kodlari,"urun_tipi_secenekleri":URUN_TIPI_CHOICES,"pricing_customer_ids":_pricing_customer_ids(),"customer_base_price_size":CUSTOMER_BASE_PRICE_SIZE}



@login_required
def showroom_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    return render(request,"product_cards/showroom_page.html",_showroom_page_context(request))

@login_required
@require_GET
def showroom_draft_load(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    return JsonResponse(_serialize_draft(_active_draft(request.user)))

@login_required
@require_POST
def showroom_draft_autosave(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    customer_id=payload.get("customer_id") or None; order_taken_by=str(payload.get("order_taken_by") or "").strip()[:120]; order_type=str(payload.get("order_type") or "SERI").strip().upper(); raw_items=payload.get("items") or []; raw_payments=payload.get("payments") or []; pricing_operations=_normalize_pricing_operations(payload.get("pricing_operations") or []); raw_target=payload.get("folio_adjustment_target"); folio_adjustment_target=None if raw_target in (None,"") else max(Decimal("0"),_decimal(raw_target,"0")); pricing_operations=_normalize_pricing_operations(payload.get("pricing_operations") or []); raw_target=payload.get("folio_adjustment_target"); folio_adjustment_target=None if raw_target in (None,"") else max(Decimal("0"),_decimal(raw_target,"0")); vat_rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("vat_rate"),"0"))); previous_balance=max(Decimal("0"),_decimal(payload.get("previous_balance"),"0"))
    if not isinstance(raw_items,list) or not isinstance(raw_payments,list): return JsonResponse({"ok":False,"message":"Föy verisi geçersiz."},status=400)
    customer=Musteri.objects.filter(pk=customer_id).first() if customer_id else None
    validation_error = _validate_customer_base_price_rows(customer, raw_items)
    if validation_error:
        return JsonResponse({"ok":False,"message":validation_error},status=400)
    with transaction.atomic():
        _lock_showroom_user(request.user)
        draft=_active_draft(request.user) or _create_draft(request.user,customer); draft.customer=customer; draft.order_taken_by=order_taken_by; draft.order_type=order_type if order_type in dict(Order.SIPARIS_TIPLERI) else "SERI"; draft.pricing_operations=pricing_operations; draft.folio_adjustment_target=folio_adjustment_target; draft.vat_rate=vat_rate; draft.previous_balance=previous_balance; draft.save(update_fields=["customer","order_taken_by","order_type","pricing_operations","folio_adjustment_target","vat_rate","previous_balance","updated_at"]); draft.items.all().delete(); create_rows=[]
        for item in raw_items:
            code=str(item.get("urun_kodu") or "").strip(); product_card=ProductCard.objects.select_related("urun").filter(urun__kod__iexact=code).first() if code else None
            if not product_card: continue
            unit_price=max(Decimal("0"),_decimal(item.get("anlasilan_fiyat"),"0")); satirlar=item.get("satirlar") or []
            if not isinstance(satirlar,list): continue
            for row in satirlar:
                color=str(row.get("renk") or "")[:120]; description=str(row.get("aciklama") or "")[:500]
                try: quantity=max(1,int(row.get("adet") or 1))
                except (TypeError,ValueError): quantity=1
                sizes=row.get("bedenler") or []
                if not isinstance(sizes,list): sizes=[]
                for size in sizes: create_rows.append(ShowroomDraftItem(draft=draft,product_card=product_card,color=color,size=str(size or "")[:120],description=description,quantity=quantity,unit_price=unit_price))
        if create_rows: ShowroomDraftItem.objects.bulk_create(create_rows)
        draft.payments.all().delete(); payment_rows=_build_payment_rows(draft,raw_payments)
        if payment_rows: ShowroomPayment.objects.bulk_create(payment_rows)
    return JsonResponse({"ok":True,"draft":draft.id,"updated_at":draft.updated_at.isoformat() if draft.updated_at else None})

@login_required
@require_POST
def showroom_draft_discount_save(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    discount_rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("discount_rate"),"0"))); discount_amount=max(Decimal("0"),_decimal(payload.get("discount_amount"),"0")); vat_rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("vat_rate"),"0")))
    with transaction.atomic():
        _lock_showroom_user(request.user)
        draft=_active_draft(request.user) or _create_draft(request.user); draft.discount_rate=discount_rate; draft.overall_discount_amount=discount_amount; draft.vat_rate=vat_rate; draft.save(update_fields=["discount_rate","overall_discount_amount","vat_rate","updated_at"])
    return JsonResponse({"ok":True,"draft":draft.id,"discount_rate":str(draft.discount_rate),"discount_amount":str(draft.overall_discount_amount),"vat_rate":str(draft.vat_rate)})

@login_required
@require_GET
def showroom_archive_list(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    kind=request.GET.get("kind"); statuses=["PENDING"] if kind=="draft" else ["APPROVED","TRANSFERRED"] if kind=="approved" else None
    if not statuses: return JsonResponse({"ok":False,"message":"Liste türü geçersiz."},status=400)
    drafts=ShowroomDraft.objects.filter(created_by=request.user,status__in=statuses).select_related("customer").prefetch_related("items","payments").order_by("-updated_at","-id")
    return JsonResponse({"ok":True,"kind":kind,"items":[_draft_summary(d) for d in drafts]})

@login_required
@require_POST
def showroom_draft_action(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    action=payload.get("action")
    try:
        with transaction.atomic():
            _lock_showroom_user(request.user)
            if action in {"save_draft","approve","delete"}:
                draft=_active_draft(request.user)
                if not draft: return JsonResponse({"ok":False,"message":"Açık bir Föy bulunmuyor."},status=400)
                if action!="delete" and not draft.items.exists(): return JsonResponse({"ok":False,"message":"Boş Föy kaydedilemez."},status=400)
                if action=="delete":
                    _delete_draft_safely(draft)
                    return JsonResponse({"ok":True,"message":"Taslak silindi."})
                draft.status="PENDING" if action=="save_draft" else "APPROVED"; draft.save(update_fields=["status","updated_at"])
                if draft.status == "APPROVED": transaction.on_commit(lambda: queue_folio_drive_sync(draft.id))
                return JsonResponse({"ok":True,"draft":draft.id,"status":draft.status,"message":"Taslak kaydedildi." if action=="save_draft" else "Föy onaylananlara kaydedildi."})
            if action=="open_saved":
                draft_id=payload.get("draft_id"); target=ShowroomDraft.objects.filter(id=draft_id,created_by=request.user,status="PENDING").first()
                if not target: return JsonResponse({"ok":False,"message":"Föy bulunamadı."},status=404)
                active=_active_draft(request.user)
                if active and active.id!=target.id:
                    if active.items.exists(): return JsonResponse({"ok":False,"message":"Önce açık Föyü taslak kaydedin, onaylayın veya silin."},status=409)
                    _delete_draft_safely(active)
                target.status="DRAFT"; target.save(update_fields=["status","updated_at"]); return JsonResponse({"ok":True,"draft":target.id,"message":"Taslak açıldı."})
            if action=="delete_saved":
                draft_id=payload.get("draft_id"); target=ShowroomDraft.objects.filter(id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED","TRANSFERRED"]).first()
                if not target: return JsonResponse({"ok":False,"message":"Föy bulunamadı."},status=404)
                _delete_draft_safely(target)
                return JsonResponse({"ok":True,"message":"Föy silindi."})
        return JsonResponse({"ok":False,"message":"İşlem geçersiz."},status=400)
    except Exception as exc:
        detail=str(exc).replace("\n"," ").strip()
        if len(detail)>500: detail=detail[-500:]
        return JsonResponse({"ok":False,"message":f"Föy işlemi tamamlanamadı [{action or 'bilinmiyor'}] {exc.__class__.__name__}: {detail}"},status=500)

@login_required
def showroom_drafts_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    return render(request,"product_cards/showroom_archive.html",{"archive_kind":"draft","archive_title":"Taslak Föyler"})

@login_required
def showroom_approved_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    return render(request,"product_cards/showroom_archive.html",{"archive_kind":"approved","archive_title":"Onaylanan Föyler"})


@login_required
def showroom_customer_folios(request, customer_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    customer = get_object_or_404(Musteri, pk=customer_id)
    drafts = _customer_folios(request.user, customer)
    status_labels = {
        "PENDING": "Taslak",
        "APPROVED": "Onaylanan",
        "TRANSFERRED": "Siparişe Aktarıldı",
    }
    folios = [
        {
            "draft": draft,
            "summary": _draft_summary(draft),
            "status_label": status_labels[draft.status],
        }
        for draft in drafts
    ]
    return render(
        request,
        "product_cards/showroom_customer_folios.html",
        {"customer": customer, "folios": folios},
    )


@login_required
@require_GET
def showroom_customer_folios_data(request, customer_id):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Bu bilgilere erişim yetkiniz yok."}, status=403)
    customer = get_object_or_404(Musteri, pk=customer_id)
    status_labels = {
        "PENDING": "Taslak",
        "APPROVED": "Onaylanan",
        "TRANSFERRED": "Siparişe Aktarıldı",
    }
    folios = []
    for draft in _customer_folios(request.user, customer):
        data = _serialize_draft(draft)
        folios.append(
            {
                "id": draft.id,
                "status": draft.status,
                "status_label": status_labels[draft.status],
                "currency": draft.currency,
                "order_taken_by": draft.order_taken_by or "",
                "updated_at": timezone.localtime(draft.updated_at).strftime("%d.%m.%Y %H:%M"),
                "summary": _draft_summary(draft),
                "items": data["items"],
            }
        )
    return JsonResponse({"ok": True, "customer": {"id": customer.id, "name": customer.ad}, "folios": folios})


@login_required
@require_GET
def showroom_customer_product_base_price(request):
    if not _can_manage(request.user):
        return JsonResponse({"ok": False, "message": "Bu bilgilere erişim yetkiniz yok."}, status=403)

    customer_id = request.GET.get("customer_id")
    product_code = str(request.GET.get("product_code") or "").strip()
    if not customer_id or not product_code:
        return JsonResponse({"ok": False, "message": "Müşteri ve ürün kodu gereklidir."}, status=400)
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "message": "Geçersiz müşteri."}, status=400)
    if not Musteri.objects.filter(pk=customer_id, aktif=True).exists():
        return JsonResponse({"ok": False, "message": "Müşteri bulunamadı."}, status=404)

    pricing_rule_exists = CustomerPricingRule.objects.filter(
        customer_id=customer_id,
        active=True,
    ).exists()
    if not pricing_rule_exists:
        return JsonResponse({"ok": True, "applies": False, "found": False})

    item = (
        ShowroomDraftItem.objects.select_related("draft")
        .filter(
            draft__created_by=request.user,
            draft__customer_id=customer_id,
            draft__status__in=["APPROVED", "TRANSFERRED"],
            product_card__urun__kod__iexact=product_code,
            size__iexact=CUSTOMER_BASE_PRICE_SIZE,
        )
        .order_by("-draft__updated_at", "-draft_id", "-id")
        .first()
    )
    if not item:
        return JsonResponse({"ok": True, "applies": True, "found": False})

    return JsonResponse({
        "ok": True,
        "applies": True,
        "found": True,
        "base_price": str(item.unit_price),
        "currency": item.draft.currency or "TRY",
        "folio_id": item.draft_id,
        "folio_updated_at": timezone.localtime(item.draft.updated_at).strftime("%d.%m.%Y %H:%M"),
    })

@login_required
def showroom_detail_page(request,draft_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    draft=get_object_or_404(ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun","payments"),id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED","TRANSFERRED"]); items=_effective_serialized_items(draft); summary=_draft_summary(draft); status_label={"PENDING":"Taslak","APPROVED":"Onaylanan","TRANSFERRED":"Siparişe Aktarıldı"}[draft.status]; back_url_name="showroom_drafts_page" if draft.status=="PENDING" else "showroom_approved_page"
    return render(request,"product_cards/showroom_detail.html",{"draft":draft,"items":items,"summary":summary,"payments":_payment_rows(draft),"status_label":status_label,"back_url_name":back_url_name})


@login_required
@require_POST
def showroom_toggle_approval(request, draft_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    with transaction.atomic():
        draft = get_object_or_404(
            ShowroomDraft.objects.select_for_update(),
            id=draft_id,
            created_by=request.user,
            status__in=["PENDING", "APPROVED", "TRANSFERRED"],
        )
        if draft.status == "PENDING":
            if not draft.items.exists():
                return HttpResponseBadRequest("Boş Föy onaylanamaz.")
            draft.status = "APPROVED"
        else:
            draft.status = "PENDING"
        draft.save(update_fields=["status", "updated_at"])
    if draft.status == "APPROVED":
        transaction.on_commit(lambda: queue_folio_drive_sync(draft.id))
    return redirect("showroom_detail_page", draft_id=draft.id)

@login_required
def showroom_edit_page(request,draft_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    draft=get_object_or_404(ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun","payments"),id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED","TRANSFERRED"]); data=_serialize_draft(draft)
    context=_showroom_page_context(request)
    context.update({"showroom_edit_mode":True,"showroom_edit_draft":draft,"showroom_edit_data":data})
    return render(request,"product_cards/showroom_page.html",context)

@login_required
@require_POST
def showroom_edit_save(request,draft_id):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    draft=get_object_or_404(ShowroomDraft,id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED","TRANSFERRED"])
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    customer_id=payload.get("customer_id") or None; order_taken_by=str(payload.get("order_taken_by") or "").strip()[:120]; order_type=str(payload.get("order_type") or "SERI").strip().upper(); raw_items=payload.get("items") or []; raw_payments=payload.get("payments") or []
    if not isinstance(raw_items,list) or not raw_items: return JsonResponse({"ok":False,"message":"Föyde en az bir ürün olmalı."},status=400)
    if not isinstance(raw_payments,list): return JsonResponse({"ok":False,"message":"Tahsilat verisi geçersiz."},status=400)
    customer=Musteri.objects.filter(pk=customer_id).first() if customer_id else None
    validation_error = _validate_customer_base_price_rows(customer, raw_items)
    if validation_error:
        return JsonResponse({"ok":False,"message":validation_error},status=400)
    rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("discount_rate"),"0"))); amount=max(Decimal("0"),_decimal(payload.get("discount_amount"),"0")); vat_rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("vat_rate"),"0"))); previous_balance=max(Decimal("0"),_decimal(payload.get("previous_balance"),"0")); create_rows=[]
    for item in raw_items:
        code=str(item.get("urun_kodu") or "").strip(); card=ProductCard.objects.select_related("urun").filter(urun__kod__iexact=code).first() if code else None
        if not card: continue
        price=max(Decimal("0"),_decimal(item.get("anlasilan_fiyat"),"0"))
        for row in item.get("satirlar") or []:
            try: qty=max(1,int(row.get("adet") or 1))
            except (TypeError,ValueError): qty=1
            for size in row.get("bedenler") or []: create_rows.append(ShowroomDraftItem(draft=draft,product_card=card,color=str(row.get("renk") or "")[:120],size=str(size or "")[:120],description=str(row.get("aciklama") or "")[:500],quantity=qty,unit_price=price))
    if not create_rows: return JsonResponse({"ok":False,"message":"Geçerli ürün satırı bulunamadı."},status=400)
    payment_rows=_build_payment_rows(draft,raw_payments)
    with transaction.atomic():
        draft.customer=customer; draft.order_taken_by=order_taken_by; draft.order_type=order_type if order_type in dict(Order.SIPARIS_TIPLERI) else "SERI"; draft.pricing_operations=pricing_operations; draft.folio_adjustment_target=folio_adjustment_target; draft.discount_rate=rate; draft.overall_discount_amount=amount; draft.vat_rate=vat_rate; draft.previous_balance=previous_balance; draft.save(update_fields=["customer","order_taken_by","order_type","pricing_operations","folio_adjustment_target","discount_rate","overall_discount_amount","vat_rate","previous_balance","updated_at"]); draft.items.all().delete(); ShowroomDraftItem.objects.bulk_create(create_rows); draft.payments.all().delete()
        if payment_rows: ShowroomPayment.objects.bulk_create(payment_rows)
    if draft.status in {"APPROVED", "TRANSFERRED"}:
        transaction.on_commit(lambda: queue_folio_drive_sync(draft.id))
    return JsonResponse({"ok":True,"message":"Föy güncellendi."})
