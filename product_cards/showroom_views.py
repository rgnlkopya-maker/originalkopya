from decimal import Decimal, InvalidOperation
import json
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from core.models import Musteri
from .models import PriceListSettings, ProductCard, ShowroomDraft, ShowroomDraftItem
from .price_list_views import _ensure_price_rates, _price_rows, _real_profit_rate


def _manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron","mudur"]).exists()


def _allowed(user):
    access=getattr(user,"moli_access",None)
    return _manager(user) or bool(access and access.can_create_orders)


def _owned_draft(user, draft_id):
    query=ShowroomDraft.objects.filter(pk=draft_id,status="DRAFT")
    if not _manager(user): query=query.filter(created_by=user)
    return get_object_or_404(query)


def _number(raw, default="0"):
    raw=(raw or default).strip().replace(",",".")
    return Decimal(raw)


def _rows(draft):
    profit=draft.profit_rate/Decimal("100"); discount=draft.discount_rate/Decimal("100")
    monthly=draft.monthly_term_rate/Decimal("100"); rows=[]
    cards=ProductCard.objects.select_related("urun").prefetch_related("materials__material").filter(price_list_active=True,urun__aktif=True).order_by("urun__kod")
    for card in cards:
        price=card.toplam_maliyet*(Decimal("1")+profit)*(Decimal("1")-discount)
        rows.append({"id":card.pk,"code":card.urun.kod,"cash":price.quantize(Decimal(".01")),
          "term3":(price*(1+monthly*3)).quantize(Decimal(".01")),"term6":(price*(1+monthly*6)).quantize(Decimal(".01")),
          "term9":(price*(1+monthly*9)).quantize(Decimal(".01")),"usd":(price/draft.usd_try).quantize(Decimal(".01")) if draft.usd_try else 0,
          "eur":(price/draft.eur_try).quantize(Decimal(".01")) if draft.eur_try else 0})
    return rows


def _draft_data(draft):
    items=[]; subtotal=Decimal("0"); selected=Decimal("0"); qty=0
    for item in draft.items.select_related("product_card__urun").all():
        line=(item.unit_price*item.quantity).quantize(Decimal(".01")); subtotal+=line; qty+=item.quantity
        if item.discount_selected:selected+=line
        items.append({"id":item.pk,"card_id":item.product_card_id,"code":item.product_card.urun.kod,"color":item.color,"size":item.size,
          "quantity":item.quantity,"unit_price":str(item.unit_price),"line_total":str(line),"discount_selected":item.discount_selected})
    eligible=subtotal if draft.discount_scope=="ALL" else selected
    discount=min(max(draft.overall_discount_amount,Decimal("0")),eligible)
    return {"id":draft.pk,"currency":draft.currency,"customer_id":draft.customer_id,"items":items,"model_count":len(items),"quantity":qty,
      "subtotal":str(subtotal.quantize(Decimal(".01"))),"discount":str(discount.quantize(Decimal(".01"))),"final_total":str((subtotal-discount).quantize(Decimal(".01"))),
      "discount_scope":draft.discount_scope}


@login_required
def showroom_page(request):
    if not _allowed(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    draft_id=request.GET.get("draft")
    draft=_owned_draft(request.user,draft_id) if draft_id else ShowroomDraft.objects.filter(created_by=request.user,status="DRAFT").first()
    if not draft:
        settings=PriceListSettings.get_solo()
        draft=ShowroomDraft.objects.create(created_by=request.user,profit_rate=settings.profit_rate,discount_rate=settings.discount_rate,
          monthly_term_rate=settings.monthly_term_rate,usd_try=settings.usd_try,eur_try=settings.eur_try)
    settings=PriceListSettings.get_solo()
    rate_error=_ensure_price_rates(settings)
    return render(request,"product_cards/showroom_draft.html",{"draft":draft,"settings":settings,"rows":_price_rows(settings,active=True),"draft_data":_draft_data(draft),
      "customers":Musteri.objects.filter(aktif=True).order_by("ad"),"rate_error":rate_error,
      "real_profit":_real_profit_rate(settings.profit_rate,settings.discount_rate)})


@login_required
@require_POST
def showroom_save(request):
    if not _allowed(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    draft=_owned_draft(request.user,request.POST.get("draft_id"))
    try:
        for field in ("profit_rate","discount_rate","monthly_term_rate","usd_try","eur_try","overall_discount_amount"):
            value=_number(request.POST.get(field)); 
            if value<0: raise ValueError("Değerler negatif olamaz.")
            if field=="discount_rate" and value>100: raise ValueError("İndirim %100'den büyük olamaz.")
            if field in ("usd_try","eur_try") and value<=0: raise ValueError("Kur sıfır olamaz.")
            setattr(draft,field,value)
        if draft.discount_rate>0 and draft.profit_rate<=0: raise ValueError("İndirim için önce kâr oranı girin.")
        if request.POST.get("currency") in ("TRY","USD","EUR"): draft.currency=request.POST["currency"]
        if request.POST.get("discount_scope") in ("ALL","SELECTED"): draft.discount_scope=request.POST["discount_scope"]
        customer=request.POST.get("customer_id"); draft.customer_id=int(customer) if customer else None
        draft.save()
    except (InvalidOperation,ValueError,TypeError) as exc:return JsonResponse({"ok":False,"message":str(exc)},status=400)
    return JsonResponse({"ok":True,"rows":[{k:str(v) if isinstance(v,Decimal) else v for k,v in x.items()} for x in _rows(draft)],"draft":_draft_data(draft)})


@login_required
@require_POST
def showroom_add_item(request):
    if not _allowed(request.user): return JsonResponse({"ok":False},status=403)
    draft=_owned_draft(request.user,request.POST.get("draft_id")); card=get_object_or_404(ProductCard,pk=request.POST.get("card_id"),price_list_active=True)
    try:
        qty=max(1,int(request.POST.get("quantity") or 1)); price=_number(request.POST.get("unit_price"))
        if price<0:raise ValueError("Fiyat negatif olamaz.")
    except (ValueError,InvalidOperation):return JsonResponse({"ok":False,"message":"Adet veya fiyat geçersiz."},status=400)
    ShowroomDraftItem.objects.create(draft=draft,product_card=card,color=(request.POST.get("color") or "").strip(),size=(request.POST.get("size") or "").strip(),quantity=qty,unit_price=price)
    return JsonResponse({"ok":True,"draft":_draft_data(draft)})


@login_required
@require_POST
def showroom_update_item(request):
    if not _allowed(request.user): return JsonResponse({"ok":False},status=403)
    draft=_owned_draft(request.user,request.POST.get("draft_id")); item=get_object_or_404(ShowroomDraftItem,pk=request.POST.get("item_id"),draft=draft)
    try:item.quantity=max(1,int(request.POST.get("quantity") or 1));item.unit_price=_number(request.POST.get("unit_price"))
    except (ValueError,InvalidOperation):return JsonResponse({"ok":False,"message":"Adet veya fiyat geçersiz."},status=400)
    item.color=(request.POST.get("color") or "").strip();item.size=(request.POST.get("size") or "").strip();item.discount_selected=request.POST.get("discount_selected")=="1";item.save()
    return JsonResponse({"ok":True,"draft":_draft_data(draft)})


@login_required
@require_POST
def showroom_delete_item(request):
    if not _allowed(request.user): return JsonResponse({"ok":False},status=403)
    draft=_owned_draft(request.user,request.POST.get("draft_id"));get_object_or_404(ShowroomDraftItem,pk=request.POST.get("item_id"),draft=draft).delete()
    return JsonResponse({"ok":True,"draft":_draft_data(draft)})


@login_required
@require_POST
def showroom_add_rows(request):
    if not _allowed(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    draft=_owned_draft(request.user,request.POST.get("draft_id"))
    card=get_object_or_404(ProductCard,pk=request.POST.get("card_id"),price_list_active=True)
    try:
        rows=json.loads(request.POST.get("rows") or "[]")
        cleaned=[]
        for row in rows:
            color=str(row.get("color") or "").strip(); size=str(row.get("size") or "").strip()
            qty=int(row.get("quantity") or 0); price=_number(str(row.get("unit_price") or "0"))
            if qty<1: continue
            if price<0: raise ValueError
            cleaned.append((color,size,qty,price))
        if not cleaned: raise ValueError
    except (ValueError,TypeError,InvalidOperation,json.JSONDecodeError):
        return JsonResponse({"ok":False,"message":"En az bir geçerli renk, beden, adet ve fiyat satırı girin."},status=400)
    with transaction.atomic():
        for color,size,qty,price in cleaned:
            ShowroomDraftItem.objects.create(draft=draft,product_card=card,color=color,size=size,quantity=qty,unit_price=price)
    return JsonResponse({"ok":True,"draft":_draft_data(draft)})


@login_required
@require_POST
def showroom_add_customer(request):
    if not _allowed(request.user): return JsonResponse({"ok":False,"message":"Yetkiniz yok."},status=403)
    name=(request.POST.get("name") or "").strip()
    if len(name)<2:return JsonResponse({"ok":False,"message":"Müşteri adını yazın."},status=400)
    customer=Musteri.objects.create(ad=name,aktif=True)
    return JsonResponse({"ok":True,"customer":{"id":customer.pk,"name":customer.ad}})
