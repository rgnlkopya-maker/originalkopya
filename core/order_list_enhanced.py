from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import close_old_connections
from django.db.models import Q, OuterRef, Subquery, DateTimeField
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
import re

from .models import Order, OrderEvent, OrderSeen, URUN_TIPI_CHOICES

STAGE_TRANSLATIONS = {
    ("malzeme_durum", "kesildi"): "Malzemesi Kesildi", ("malzeme_durum", "boyandi"): "Malzemesi Boyandı", ("malzeme_durum", "eksik"): "Malzemesi Eksik",
    ("kesim_durum", "siraya_alindi"): "Kesim Sırasına Alındı", ("kesim_durum", "basladi"): "Kesim Başladı", ("kesim_durum", "kismi"): "Kısmi Kesim yapıldı", ("kesim_durum", "bitti"): "Kesildi",
    ("dikim_durum", "siraya_alindi"): "Dikim Sırasına Alındı", ("dikim_durum", "basladi"): "Dikim Başladı", ("dikim_durum", "kismi"): "Kısmi Dikim yapıldı", ("dikim_durum", "bitti"): "Dikildi",
    ("dikim_fason_durumu", "verildi"): "Fason Dikime Verildi", ("dikim_fason_durumu", "alindi"): "Fason Dikimden Alındı", ("nakis_durum", "verildi"): "Nakışa Verildi", ("nakis_durum", "alindi"): "Nakıştan Alındı",
    ("susleme_durum", "siraya_alindi"): "Süsleme Sırasına Alındı", ("susleme_durum", "basladi"): "Süsleme Başladı", ("susleme_durum", "kismi"): "Kısmi Süsleme", ("susleme_durum", "bitti"): "Süslendi",
    ("susleme_fason_durumu", "verildi"): "Fason Süslemeye Verildi", ("susleme_fason_durumu", "alindi"): "Fason Süslemeden Alındı",
    ("sevkiyat_durum", "gonderildi"): "Sevkedildi", ("sevkiyat_durum", "depoya"): "Depoya Girdi", ("sevkiyat_durum", "kargodan_geri_geldi"): "Kargodan Geri Geldi", ("sevkiyat_durum", "iade_geldi"): "İade Geldi",
    ("sevkiyat_durum", "yanlis_sevkiyat"): "Yanlış Sevkiyat", ("sevkiyat_durum", "tekrar_gonderildi"): "Tekrar Gönderildi",
}

def _normalize(value):
    if not value: return ""
    return (value.lower().replace("ı","i").replace("ö","o").replace("ü","u").replace("ş","s").replace("ç","c").replace("ğ","g").strip())

def _multi(request,key): return [v for v in request.GET.getlist(key) if v != ""]

def _transfer_status(stage, value, parca):
    stage_n = _normalize(stage).replace(" ", "_")
    if stage_n not in {"uretim_aktarimi", "uretim_aktarimı"} and "uretim_aktar" not in stage_n:
        return None
    value = value or ""
    value_n = _normalize(value)
    number = (parca or "").strip()
    if not number:
        m = re.search(r"([^\s]+)\s+sipariş(?:ine|inden)", value, re.IGNORECASE)
        if m: number = m.group(1).strip()
        else:
            m = re.search(r"^([^\s]+?)(?:'|’)?(?:e|a|ye|ya|den|dan|ten|tan)\s+(?:verildi|alındı|alindi)", value, re.IGNORECASE)
            if m: number = m.group(1).strip()
    number = number or "Sipariş"
    if "alindi" in value_n or "siparisinden" in value_n:
        return f"{number}'den alındı"
    return f"{number}'e verildi"

@never_cache
@login_required
def order_list(request):
    close_old_connections()
    all_orders=Order.objects.only("id","last_updated"); total_count=Order.objects.count(); seen_map={s.order_id:s.seen_time for s in OrderSeen.objects.filter(user=request.user)}
    new_flags={o.id:(seen_map.get(o.id) is None or o.last_updated>seen_map[o.id]) for o in all_orders}
    if hasattr(request.user,"userprofile"):
        request.user.userprofile.last_seen_orders=timezone.now(); request.user.userprofile.save(update_fields=["last_seen_orders"])
    latest_event=(OrderEvent.objects.filter(order=OuterRef("pk")).exclude(event_type="order_update").exclude(stage__in=["satis_fiyati","ekstra_maliyet","maliyet_override","maliyet_uygulanan"]).order_by("-timestamp","-id")[:1])
    base_qs=(Order.objects.select_related("musteri").annotate(latest_stage=Subquery(latest_event.values("stage")),latest_value=Subquery(latest_event.values("value")),latest_parca=Subquery(latest_event.values("parca")),last_status_date=Subquery(latest_event.values("timestamp"),output_field=DateTimeField())).order_by("-id")); qs=base_qs
    active_values=_multi(request,"active") or ["1"]
    if "all" not in active_values and not ("1" in active_values and "0" in active_values):
        if "1" in active_values: qs=qs.filter(is_active=True)
        elif "0" in active_values: qs=qs.filter(is_active=False)
    multi_filters={"siparis_numarasi__in":_multi(request,"siparis_no"),"musteri__ad__in":_multi(request,"musteri"),"urun_kodu__in":_multi(request,"urun_kodu"),"urun_tipi__in":_multi(request,"urun_tipi"),"renk__in":_multi(request,"renk"),"beden__in":_multi(request,"beden"),"siparis_tipi__in":_multi(request,"siparis_tipi"),"musteri_referans__in":_multi(request,"musteri_referans")}
    for field,values in multi_filters.items():
        if values: qs=qs.filter(**{field:values})
    status_filter=_multi(request,"status")
    if status_filter:
        status_q=Q()
        for pair,label in STAGE_TRANSLATIONS.items():
            if label in status_filter: status_q|=Q(latest_stage=pair[0],latest_value=pair[1])
        qs=qs.filter(status_q)
    sb=request.GET.get("siparis_tarihi_baslangic","").strip(); se=request.GET.get("siparis_tarihi_bitis","").strip(); tb=request.GET.get("teslim_tarihi_baslangic","").strip(); te=request.GET.get("teslim_tarihi_bitis","").strip(); db=request.GET.get("son_durum_tarihi_baslangic","").strip(); de=request.GET.get("son_durum_tarihi_bitis","").strip()
    if sb: qs=qs.filter(siparis_tarihi__gte=sb)
    if se: qs=qs.filter(siparis_tarihi__lte=se)
    if tb: qs=qs.filter(teslim_tarihi__gte=tb)
    if te: qs=qs.filter(teslim_tarihi__lte=te)
    if db: qs=qs.filter(last_status_date__date__gte=db)
    if de: qs=qs.filter(last_status_date__date__lte=de)
    kalite=request.GET.get("kalite","").strip()
    if kalite=="acik": qs=qs.filter(quality_issues__durum="ACIK").distinct()
    elif kalite=="var": qs=qs.filter(quality_issues__isnull=False).distinct()
    elif kalite=="yok": qs=qs.filter(quality_issues__isnull=True)
    aktif_count=base_qs.filter(is_active=True).count(); pasif_count=base_qs.filter(is_active=False).count(); sevke_count=base_qs.filter(is_active=True,latest_stage="sevkiyat_durum",latest_value="gonderildi").count(); filtered_count=qs.count()
    paginator=Paginator(qs,50); page_obj=paginator.get_page(request.GET.get("page"))
    for order in page_obj:
        order.is_new=new_flags.get(order.id,False)
        if not order.latest_stage or not order.latest_value: order.formatted_status="-"; continue
        transfer_status=_transfer_status(order.latest_stage,order.latest_value,order.latest_parca)
        if transfer_status: order.formatted_status=transfer_status; continue
        key=(_normalize(order.latest_stage),_normalize(order.latest_value))
        if key in STAGE_TRANSLATIONS: order.formatted_status=STAGE_TRANSLATIONS[key]
        else:
            nice_stage=(order.latest_stage.replace("_durum","").replace("_fason_durumu"," Fason").replace("_"," ").title()); order.formatted_status=f"{nice_stage} → {order.latest_value.replace('_',' ').title()}"
    context={"orders":page_obj,"siparis_options":Order.objects.values_list("siparis_numarasi",flat=True).distinct().order_by("siparis_numarasi"),"musteri_options":Order.objects.values_list("musteri__ad",flat=True).distinct().order_by("musteri__ad"),"urun_options":Order.objects.values_list("urun_kodu",flat=True).distinct().order_by("urun_kodu"),"urun_tipi_options":URUN_TIPI_CHOICES,"renk_options":Order.objects.values_list("renk",flat=True).distinct().order_by("renk"),"beden_options":Order.objects.values_list("beden",flat=True).distinct().order_by("beden"),"musteri_referans_options":Order.objects.exclude(musteri_referans__isnull=True).exclude(musteri_referans__exact="").values_list("musteri_referans",flat=True).distinct().order_by("musteri_referans"),"status_options":sorted(set(STAGE_TRANSLATIONS.values())),"siparis_tipi_options":Order.SIPARIS_TIPLERI,"total_count":total_count,"filtered_count":filtered_count,"aktif_count":aktif_count,"pasif_count":pasif_count,"sevke_count":sevke_count,"is_manager":request.user.is_superuser or request.user.groups.filter(name__in=["patron","mudur"]).exists(),"request":request}
    response=render(request,"core/order_list.html",context); response["Cache-Control"]="no-cache, no-store, must-revalidate"; response["Pragma"]="no-cache"; response["Expires"]="0"; return response
