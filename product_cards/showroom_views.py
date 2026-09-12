import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import Beden, Musteri, Renk, URUN_TIPI_CHOICES, UrunKod
from .models import PriceListSettings, ProductCard, ShowroomDraft, ShowroomDraftItem
from .payment_models import ShowroomPayment
from .price_list_views import _can_manage, _ensure_price_rates, _price_rows, _real_profit_rate


def _active_draft(user):
    return ShowroomDraft.objects.filter(created_by=user, status="DRAFT").order_by("-updated_at", "-id").first()


def _decimal(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _create_draft(user, customer=None):
    settings = PriceListSettings.get_solo()
    return ShowroomDraft.objects.create(created_by=user, customer=customer, status="DRAFT", currency="TRY", profit_rate=settings.profit_rate, discount_rate=Decimal("0"), monthly_term_rate=settings.monthly_term_rate, usd_try=settings.usd_try, eur_try=settings.eur_try, overall_discount_amount=Decimal("0"))


def _payment_data(draft):
    if not draft: return []
    return [{"entry_type":p.entry_type,"method":p.method,"amount":str(p.amount),"payment_date":p.payment_date.isoformat() if p.payment_date else "","due_date":p.due_date.isoformat() if p.due_date else "","note":p.note} for p in draft.payments.all().order_by("due_date","payment_date","id")]


def _serialize_draft(draft):
    if not draft:
        return {"ok": True, "draft": None, "customer_id": "", "items": [], "payments": [], "discount_rate": "0", "discount_amount": "0"}
    groups=[]; group_map={}; row_maps={}
    for db_item in draft.items.select_related("product_card__urun").order_by("created_at", "id"):
        code=db_item.product_card.urun.kod; unit_price=str(db_item.unit_price); group_key=(db_item.product_card_id,unit_price)
        if group_key not in group_map:
            group_map[group_key]=len(groups); groups.append({"urun_kodu":code,"anlasilan_fiyat":unit_price,"satirlar":[]}); row_maps[group_key]={}
        group=groups[group_map[group_key]]; row_key=(db_item.color,db_item.quantity,db_item.description)
        if row_key not in row_maps[group_key]:
            row_maps[group_key][row_key]=len(group["satirlar"]); group["satirlar"].append({"renk":db_item.color,"bedenler":[],"adet":db_item.quantity,"aciklama":db_item.description})
        group["satirlar"][row_maps[group_key][row_key]]["bedenler"].append(db_item.size)
    return {"ok":True,"draft":draft.id,"customer_id":str(draft.customer_id or ""),"items":groups,"payments":_payment_data(draft),"discount_rate":str(draft.discount_rate or 0),"discount_amount":str(draft.overall_discount_amount or 0),"updated_at":draft.updated_at.isoformat() if draft.updated_at else None}


def _draft_summary(draft):
    line_total=ExpressionWrapper(F("quantity")*F("unit_price"),output_field=DecimalField(max_digits=20,decimal_places=2))
    items=draft.items.aggregate(product_count=Count("product_card",distinct=True),total_qty=Sum("quantity"),subtotal=Sum(line_total)); subtotal=items["subtotal"] or Decimal("0")
    discount=subtotal*draft.discount_rate/Decimal("100") if draft.discount_rate and draft.discount_rate>0 else draft.overall_discount_amount or Decimal("0")
    discount=min(subtotal,max(Decimal("0"),discount)); total=max(Decimal("0"),subtotal-discount)
    collected=draft.payments.filter(entry_type="COLLECTION").aggregate(v=Sum("amount"))["v"] or Decimal("0"); promised=draft.payments.filter(entry_type="PROMISE").aggregate(v=Sum("amount"))["v"] or Decimal("0"); remaining=max(Decimal("0"),total-collected)
    return {"id":draft.id,"customer":draft.customer.ad if draft.customer else "Müşteri seçilmedi","product_count":items["product_count"] or 0,"total_qty":items["total_qty"] or 0,"subtotal":str(subtotal.quantize(Decimal("0.01"))),"discount":str(discount.quantize(Decimal("0.01"))),"total":str(total.quantize(Decimal("0.01"))),"collected":str(collected.quantize(Decimal("0.01"))),"promised":str(promised.quantize(Decimal("0.01"))),"remaining":str(remaining.quantize(Decimal("0.01"))),"updated_at":timezone.localtime(draft.updated_at).strftime("%d.%m.%Y %H:%M"),"status":draft.status}


def _payment_rows(draft): return list(draft.payments.all().order_by("due_date","payment_date","id"))

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

@login_required
def showroom_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    settings=PriceListSettings.get_solo()
    if settings.profit_rate<=0 and settings.discount_rate>0: settings.discount_rate=Decimal("0"); settings.save(update_fields=["discount_rate","updated_at"])
    rate_error=_ensure_price_rates(settings); show_inactive=request.GET.get("durum")=="pasif"; musteriler=Musteri.objects.filter(aktif=True).order_by("ad"); renkler=Renk.objects.filter(aktif=True).order_by("ad"); bedenler=Beden.objects.filter(aktif=True).order_by("ad"); urun_kodlari=UrunKod.objects.filter(aktif=True).order_by("kod")
    return render(request,"product_cards/showroom_page.html",{"settings":settings,"rows":_price_rows(settings,active=not show_inactive),"show_inactive":show_inactive,"inactive_count":ProductCard.objects.filter(price_list_active=False).count(),"rate_error":rate_error,"real_profit_rate":_real_profit_rate(settings.profit_rate,settings.discount_rate),"showroom_mode":True,"musteriler":musteriler,"renkler":renkler,"bedenler":bedenler,"urun_kodlari":urun_kodlari,"aktif_musteriler":musteriler,"aktif_renkler":renkler,"aktif_bedenler":bedenler,"aktif_urun_kodlari":urun_kodlari,"urun_tipi_secenekleri":URUN_TIPI_CHOICES})

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
    customer_id=payload.get("customer_id") or None; raw_items=payload.get("items") or []; raw_payments=payload.get("payments") or []
    if not isinstance(raw_items,list) or not isinstance(raw_payments,list): return JsonResponse({"ok":False,"message":"Föy verisi geçersiz."},status=400)
    customer=Musteri.objects.filter(pk=customer_id).first() if customer_id else None
    with transaction.atomic():
        draft=_active_draft(request.user) or _create_draft(request.user,customer); draft.customer=customer; draft.save(update_fields=["customer","updated_at"]); draft.items.all().delete(); create_rows=[]
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
    discount_rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("discount_rate"),"0"))); discount_amount=max(Decimal("0"),_decimal(payload.get("discount_amount"),"0")); draft=_active_draft(request.user) or _create_draft(request.user); draft.discount_rate=discount_rate; draft.overall_discount_amount=discount_amount; draft.save(update_fields=["discount_rate","overall_discount_amount","updated_at"])
    return JsonResponse({"ok":True,"draft":draft.id,"discount_rate":str(draft.discount_rate),"discount_amount":str(draft.overall_discount_amount)})

@login_required
@require_GET
def showroom_archive_list(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    kind=request.GET.get("kind"); status="PENDING" if kind=="draft" else "APPROVED" if kind=="approved" else None
    if not status: return JsonResponse({"ok":False,"message":"Liste türü geçersiz."},status=400)
    drafts=ShowroomDraft.objects.filter(created_by=request.user,status=status).select_related("customer").prefetch_related("items","payments").order_by("-updated_at","-id")
    return JsonResponse({"ok":True,"kind":kind,"items":[_draft_summary(d) for d in drafts]})

@login_required
@require_POST
def showroom_draft_action(request):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    action=payload.get("action")
    with transaction.atomic():
        if action in {"save_draft","approve","delete"}:
            draft=_active_draft(request.user)
            if not draft: return JsonResponse({"ok":False,"message":"Açık bir Föy bulunmuyor."},status=400)
            if action!="delete" and not draft.items.exists(): return JsonResponse({"ok":False,"message":"Boş Föy kaydedilemez."},status=400)
            if action=="delete": draft.delete(); return JsonResponse({"ok":True,"message":"Taslak silindi."})
            draft.status="PENDING" if action=="save_draft" else "APPROVED"; draft.save(update_fields=["status","updated_at"]); return JsonResponse({"ok":True,"draft":draft.id,"status":draft.status,"message":"Taslak kaydedildi." if action=="save_draft" else "Föy onaylananlara kaydedildi."})
        if action=="open_saved":
            draft_id=payload.get("draft_id"); target=ShowroomDraft.objects.filter(id=draft_id,created_by=request.user,status="PENDING").first()
            if not target: return JsonResponse({"ok":False,"message":"Föy bulunamadı."},status=404)
            active=_active_draft(request.user)
            if active and active.id!=target.id:
                if active.items.exists(): return JsonResponse({"ok":False,"message":"Önce açık Föyü taslak kaydedin, onaylayın veya silin."},status=409)
                active.delete()
            target.status="DRAFT"; target.save(update_fields=["status","updated_at"]); return JsonResponse({"ok":True,"draft":target.id,"message":"Taslak açıldı."})
        if action=="delete_saved":
            draft_id=payload.get("draft_id"); target=ShowroomDraft.objects.filter(id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED"]).first()
            if not target: return JsonResponse({"ok":False,"message":"Föy bulunamadı."},status=404)
            target.delete(); return JsonResponse({"ok":True,"message":"Föy silindi."})
    return JsonResponse({"ok":False,"message":"İşlem geçersiz."},status=400)

@login_required
def showroom_drafts_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    return render(request,"product_cards/showroom_archive.html",{"archive_kind":"draft","archive_title":"Taslak Föyler"})

@login_required
def showroom_approved_page(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    return render(request,"product_cards/showroom_archive.html",{"archive_kind":"approved","archive_title":"Onaylanan Föyler"})

@login_required
def showroom_detail_page(request,draft_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    draft=get_object_or_404(ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun","payments"),id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED"]); data=_serialize_draft(draft); summary=_draft_summary(draft); status_label="Taslak" if draft.status=="PENDING" else "Onaylanan"; back_url_name="showroom_drafts_page" if draft.status=="PENDING" else "showroom_approved_page"
    return render(request,"product_cards/showroom_detail.html",{"draft":draft,"items":data["items"],"summary":summary,"payments":_payment_rows(draft),"status_label":status_label,"back_url_name":back_url_name})

@login_required
def showroom_edit_page(request,draft_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    draft=get_object_or_404(ShowroomDraft.objects.select_related("customer").prefetch_related("items__product_card__urun","payments"),id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED"]); data=_serialize_draft(draft)
    return render(request,"product_cards/showroom_edit.html",{"draft":draft,"items":data["items"],"payments":_payment_rows(draft),"musteriler":Musteri.objects.filter(aktif=True).order_by("ad"),"renkler":Renk.objects.filter(aktif=True).order_by("ad"),"bedenler":Beden.objects.filter(aktif=True).order_by("ad")})

@login_required
@require_POST
def showroom_edit_save(request,draft_id):
    if not _can_manage(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    draft=get_object_or_404(ShowroomDraft,id=draft_id,created_by=request.user,status__in=["PENDING","APPROVED"])
    try: payload=json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError,UnicodeDecodeError): return JsonResponse({"ok":False,"message":"Geçersiz veri."},status=400)
    customer_id=payload.get("customer_id") or None; raw_items=payload.get("items") or []; raw_payments=payload.get("payments") or []
    if not isinstance(raw_items,list) or not raw_items: return JsonResponse({"ok":False,"message":"Föyde en az bir ürün olmalı."},status=400)
    if not isinstance(raw_payments,list): return JsonResponse({"ok":False,"message":"Tahsilat verisi geçersiz."},status=400)
    customer=Musteri.objects.filter(pk=customer_id).first() if customer_id else None; rate=max(Decimal("0"),min(Decimal("100"),_decimal(payload.get("discount_rate"),"0"))); amount=max(Decimal("0"),_decimal(payload.get("discount_amount"),"0")); create_rows=[]
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
        draft.customer=customer; draft.discount_rate=rate; draft.overall_discount_amount=amount; draft.save(update_fields=["customer","discount_rate","overall_discount_amount","updated_at"]); draft.items.all().delete(); ShowroomDraftItem.objects.bulk_create(create_rows); draft.payments.all().delete()
        if payment_rows: ShowroomPayment.objects.bulk_create(payment_rows)
    return JsonResponse({"ok":True,"message":"Föy güncellendi."})