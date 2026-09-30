from app_settings.access import data_scope_value
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import close_old_connections
from django.db.models import Q, OuterRef, Subquery, DateTimeField
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
import re

from .models import Order, OrderEvent, OrderFlag, URUN_TIPI_CHOICES

STAGE_TRANSLATIONS = {
    ("malzeme_durum", "kesildi"): "Malzemesi Kesildi", ("malzeme_durum", "boyandi"): "Malzemesi Boyandı", ("malzeme_durum", "eksik"): "Malzemesi Eksik",
    ("kesim_durum", "siraya_alindi"): "Kesim Sırasına Alındı", ("kesim_durum", "basladi"): "Kesim Başladı", ("kesim_durum", "kismi"): "Kısmi Kesim yapıldı", ("kesim_durum", "bitti"): "Kesildi",
    ("dikim_durum", "siraya_alindi"): "Dikim Sırasına Alındı", ("dikim_durum", "basladi"): "Dikim Başladı", ("dikim_durum", "kismi"): "Kısmi Dikim yapıldı", ("dikim_durum", "bitti"): "Dikildi",
    ("dikim_fason_durumu", "verildi"): "Fason Dikime Verildi", ("dikim_fason_durumu", "alindi"): "Fason Dikimden Alındı", ("nakis_durum", "verildi"): "Nakışa Verildi", ("nakis_durum", "alindi"): "Nakıştan Alındı",
    ("susleme_durum", "siraya_alindi"): "Süsleme Sırasına Alındı", ("susleme_durum", "basladi"): "Süsleme Başladı", ("susleme_durum", "kismi"): "Kısmi Süsleme", ("susleme_durum", "bitti"): "Süslendi",
    ("susleme_fason_durumu", "verildi"): "Fason Süslemeye Verildi", ("susleme_fason_durumu", "alindi"): "Fason Süslemeden Alındı",
    ("sevkiyat_durum", "gonderildi"): "Sevkedildi", ("sevkiyat_durum", "depoya"): "Depoya Girdi", ("sevkiyat_durum", "kargodan_geri_geldi"): "Kargodan Geri Geldi", ("sevkiyat_durum", "iade_geldi"): "İade Geldi",
    ("sevkiyat_durum", "yanlis_sevkiyat"): "Yanlış Sevkiyat", ("sevkiyat_durum", "tekrar_gonderildi"): "Tekrar Gönderildi",
    ("konsinye_durum", "verildi"): "Konsinyeye Verildi", ("konsinye_durum", "geri_geldi"): "Konsinyeden Geri Geldi",
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
    scope_orders = data_scope_value(request.user, "orders")
    all_orders = Order.objects.only("id")
    if scope_orders == "active_only":
        all_orders = all_orders.filter(is_active=True)
    total_count = all_orders.count()
    if hasattr(request.user,"userprofile"):
        request.user.userprofile.last_seen_orders=timezone.now(); request.user.userprofile.save(update_fields=["last_seen_orders"])
    latest_event=(OrderEvent.objects.filter(order=OuterRef("pk")).exclude(event_type="order_update").exclude(stage__in=["satis_fiyati","ekstra_maliyet","maliyet_indirimi","maliyet_override","maliyet_uygulanan"]).order_by("-timestamp","-id")[:1])
    base_qs=(Order.objects.select_related("musteri").annotate(latest_stage=Subquery(latest_event.values("stage")),latest_value=Subquery(latest_event.values("value")),latest_parca=Subquery(latest_event.values("parca")),last_status_date=Subquery(latest_event.values("timestamp"),output_field=DateTimeField())).order_by("-id"))
    if scope_orders == "active_only":
        base_qs = base_qs.filter(is_active=True)
    qs=base_qs
    active_values=_multi(request,"active") or ["1"]
    if "all" not in active_values and not ("1" in active_values and "0" in active_values):
        if "1" in active_values: qs=qs.filter(is_active=True)
        elif "0" in active_values: qs=qs.filter(is_active=False)
    q=request.GET.get("q","").strip()
    if q:
        # Akıllı arama: boşlukla ayrılan her kelime siparişin herhangi bir
        # aranabilir alanında bulunmalı. Örn. "7138 taş" => hem 7138 hem taş.
        # icontains PostgreSQL/Django tarafında büyük-küçük harf duyarsızdır.
        search_fields = (
            "siparis_numarasi", "musteri__ad", "urun_kodu", "urun_tipi",
            "siparis_tipi", "musteri_referans", "renk", "beden", "aciklama",
            "latest_value",
        )
        for term in q.split():
            term_q = Q()
            for field in search_fields:
                term_q |= Q(**{f"{field}__icontains": term})
            if term.isdigit():
                term_q |= Q(adet=int(term))
            qs=qs.filter(term_q)

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
    etiket=request.GET.get("etiket","").strip()
    if etiket=="printed": qs=qs.filter(cikti_alindi=True)
    elif etiket=="unprinted": qs=qs.filter(cikti_alindi=False)

    kalite=request.GET.get("kalite","").strip()
    if kalite=="acik": qs=qs.filter(quality_issues__durum="ACIK").distinct()
    elif kalite=="var": qs=qs.filter(quality_issues__isnull=False).distinct()
    elif kalite=="yok": qs=qs.filter(quality_issues__isnull=True)
    flag_filter=request.GET.get("bayrak","").strip()
    if flag_filter=="1":
        visible_flag_orders = OrderFlag.objects.filter(
            Q(created_by=request.user) | Q(notify_users=request.user),
            is_active=True,
        ).values_list("order_id", flat=True)
        qs=qs.filter(id__in=visible_flag_orders).distinct()
    aktif_count=base_qs.filter(is_active=True).count(); pasif_count=base_qs.filter(is_active=False).count(); sevke_count=base_qs.filter(is_active=True,latest_stage="sevkiyat_durum",latest_value="gonderildi").count()
    # Grafik görünümü tablodaki Son Durum ile birebir aynı latest_stage/latest_value kaynağını kullanır.
    # Sayfalama öncesi hesaplanır; böylece grafik filtreye uyan TÜM siparişleri gösterir.
    graph_groups = [
        ("no_action", "İşlem Yok", set()),
        ("material", "Malzeme", {"malzeme_durum"}),
        ("cutting", "Kesim", {"kesim_durum"}),
        ("sewing", "Dikim", {"dikim_durum"}),
        ("embroidery_outsource", "Nakış / Fason", {"nakis_durum", "dikim_fason_durumu", "susleme_fason_durumu"}),
        ("embellishment", "Süsleme", {"susleme_durum"}),
        ("warehouse", "Hazır ve Sevkiyat", {"sevkiyat_durum", "konsinye_durum"}),
    ]
    graph_stage = request.GET.get("graph_stage", "").strip()
    graph_status = request.GET.get("graph_status", "").strip()

    graph = {key: {"key": key, "label": label, "count": 0, "orders": [], "details": {}} for key, label, _ in graph_groups}
    graph_total = qs.count()
    graph_rows = qs.values("id","siparis_numarasi","musteri__ad","urun_kodu","renk","beden","latest_stage","latest_value","latest_parca")
    for row in graph_rows:
        stage = row["latest_stage"] or ""
        value = row["latest_value"] or ""
        if not stage or not value:
            key = "no_action"
            detail = "Hiç işlem yapılmadı"
        else:
            key = next((k for k, _, stages in graph_groups if stage in stages), "no_action")
            detail = STAGE_TRANSLATIONS.get((stage, value)) or _transfer_status(stage, value, row["latest_parca"]) or value.replace("_"," ").title()
        item = {
            "id": row["id"], "no": row["siparis_numarasi"] or "-", "customer": row["musteri__ad"] or "-",
            "product": row["urun_kodu"] or "-", "color": row["renk"] or "-", "size": row["beden"] or "-",
            "detail": detail,
        }
        graph[key]["orders"].append(item)
        graph[key]["count"] += 1
        graph[key]["details"][detail] = graph[key]["details"].get(detail, 0) + 1

    graph_data = []
    graph_detail_data = []
    graph_stage_label = ""
    for key, label, _ in graph_groups:
        bucket = graph[key]
        bucket["percent"] = round((bucket["count"] / graph_total * 100), 1) if graph_total else 0
        bucket["details"] = [{"label": k, "count": v, "percent": round((v / bucket["count"] * 100), 1) if bucket["count"] else 0} for k, v in sorted(bucket["details"].items(), key=lambda x: (-x[1], x[0]))]
        graph_data.append(bucket)
        if key == graph_stage:
            graph_stage_label = label
            graph_detail_data = bucket["details"]

    # Alt durum seçilince aynı Sipariş Listesi görünümünde yalnızca o siparişleri göster.
    if graph_stage and graph_status:
        bucket = graph.get(graph_stage)
        matching_ids = [o["id"] for o in (bucket["orders"] if bucket else []) if o["detail"] == graph_status]
        qs = qs.filter(id__in=matching_ids)

    filtered_count = qs.count()

    paginator=Paginator(qs,50); page_obj=paginator.get_page(request.GET.get("page"))
    page_order_ids = [o.id for o in page_obj.object_list]
    visible_flag_order_ids = set(
        OrderFlag.objects.filter(
            Q(created_by=request.user) | Q(notify_users=request.user),
            is_active=True,
            order_id__in=page_order_ids,
        ).values_list("order_id", flat=True).distinct()
    )
    for order in page_obj:
        order.has_visible_flag = order.id in visible_flag_order_ids
        if not order.latest_stage or not order.latest_value: order.formatted_status="-"; continue
        transfer_status=_transfer_status(order.latest_stage,order.latest_value,order.latest_parca)
        if transfer_status: order.formatted_status=transfer_status; continue
        key=(_normalize(order.latest_stage),_normalize(order.latest_value))
        if key in STAGE_TRANSLATIONS: order.formatted_status=STAGE_TRANSLATIONS[key]
        else:
            nice_stage=(order.latest_stage.replace("_durum","").replace("_fason_durumu"," Fason").replace("_"," ").title()); order.formatted_status=f"{nice_stage} → {order.latest_value.replace('_',' ').title()}"
    selected_order_types=_multi(request,"siparis_tipi")
    quick_order_type=selected_order_types[0] if len(selected_order_types)==1 and selected_order_types[0] in {"OZEL","SERI","TEKLI","STOK","KONSINYE"} else "ALL"
    quick_flag_filter=request.GET.get("bayrak","").strip()=="1"
    context={"orders":page_obj,"siparis_options":Order.objects.values_list("siparis_numarasi",flat=True).distinct().order_by("siparis_numarasi"),"musteri_options":Order.objects.values_list("musteri__ad",flat=True).distinct().order_by("musteri__ad"),"urun_options":Order.objects.values_list("urun_kodu",flat=True).distinct().order_by("urun_kodu"),"urun_tipi_options":URUN_TIPI_CHOICES,"renk_options":Order.objects.values_list("renk",flat=True).distinct().order_by("renk"),"beden_options":Order.objects.values_list("beden",flat=True).distinct().order_by("beden"),"musteri_referans_options":Order.objects.exclude(musteri_referans__isnull=True).exclude(musteri_referans__exact="").values_list("musteri_referans",flat=True).distinct().order_by("musteri_referans"),"status_options":sorted(set(STAGE_TRANSLATIONS.values())),"siparis_tipi_options":Order.SIPARIS_TIPLERI,"quick_order_type":quick_order_type,"quick_flag_filter":quick_flag_filter,"total_count":total_count,"filtered_count":filtered_count,"aktif_count":aktif_count,"pasif_count":pasif_count,"sevke_count":sevke_count,"is_manager":request.user.is_superuser or request.user.groups.filter(name__in=["patron","mudur"]).exists(),"graph_data":graph_data,"graph_detail_data":graph_detail_data,"graph_stage":graph_stage,"graph_stage_label":graph_stage_label,"graph_status":graph_status,"graph_total":graph_total,"request":request}
    response=render(request,"core/order_list.html",context); response["Cache-Control"]="no-cache, no-store, must-revalidate"; response["Pragma"]="no-cache"; response["Expires"]="0"; return response
