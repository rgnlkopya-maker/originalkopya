# ========================
# ✅ Python
# ========================
import os
import time
import json
from datetime import datetime, timedelta
from decimal import Decimal
from collections import Counter, defaultdict

# ========================
# ✅ Django
# ========================
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connections, close_old_connections
from django.db.models import (
    Q, F, Max, Sum, Count, Value, Case, When,
    Subquery, OuterRef, DecimalField, ExpressionWrapper, CharField, DateTimeField
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# ========================
# ✅ App Imports
# ========================
from .models import (
    Order, Musteri, Nakisci, Fasoncu, DepoStok,
    OrderEvent, OrderSeen, UretimGecmisi,
    Notification, ProductCost, OrderImage,
    UserProfile, Renk, Beden, UrunKod, MesaiKayit, URUN_TIPI_CHOICES
)
from .forms import OrderForm, MusteriForm

# ✅ QR util (buraya koy)

DEC = DecimalField(max_digits=12, decimal_places=2)
ZERO = Value(Decimal("0.00"), output_field=DEC)



# ========================
# 📌 MODELLER (TÜMÜ TEK PARÇA)
# ========================
from .models import (
    Order,
    Musteri,
    Nakisci,
    Fasoncu,
    DepoStok,
    OrderEvent,
    OrderSeen,
    UretimGecmisi,
    Notification,
    ProductCost,
    OrderImage,
    UserProfile,
    Renk,
    Beden,
    UrunKod,
)

# ========================
# 📌 FORMLAR
# ========================
from .forms import OrderForm, MusteriForm

# ========================
# 📌 DJANGO TEMEL IMPORTLAR
# ========================
from django.db import connections
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import (
    Q, Max, Count, Sum, F, ExpressionWrapper, FloatField,
    Subquery, OuterRef, DecimalField
)
from django.db.models.functions import Coalesce
from django.http import (
    HttpResponse, JsonResponse, HttpResponseForbidden
)
from django.shortcuts import (
    render, redirect, get_object_or_404
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# ========================
# 📌 DİĞER
# ========================
from openpyxl import Workbook
from decimal import Decimal

# -------------------------------
# 🌐 Türkçe karakter normalize fonksiyonu
# -------------------------------
def normalize(v):
    if not v:
        return ""
    return (
        v.lower()
         .replace("ı", "i")
         .replace("ö", "o")
         .replace("ü", "u")
         .replace("ş", "s")
         .replace("ç", "c")
         .replace("ğ", "g")
         .strip()
    )






# 🧠 Ortak filtreleme fonksiyonu
def apply_filters(request, qs):
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(siparis_numarasi__icontains=q)
            | Q(siparis_tipi__icontains=q)
            | Q(musteri__ad__icontains=q)
            | Q(urun_kodu__icontains=q)
            | Q(renk__icontains=q)
            | Q(beden__icontains=q)
            | Q(adet__icontains=q)
            | Q(siparis_tarihi__icontains=q)
            | Q(teslim_tarihi__icontains=q)
            | Q(aciklama__icontains=q)
        )

    filter_fields = {
        "siparis_tipi__in": request.GET.getlist("siparis_tipi"),
        "musteri__ad__in": request.GET.getlist("musteri"),
        "urun_kodu__in": request.GET.getlist("urun_kodu"),
        "renk__in": request.GET.getlist("renk"),
        "beden__in": request.GET.getlist("beden"),
        "adet__in": request.GET.getlist("adet"),
        "siparis_tarihi__in": request.GET.getlist("siparis_tarihi"),
        "teslim_tarihi__in": request.GET.getlist("teslim_tarihi"),
        "aciklama__in": request.GET.getlist("aciklama"),
    }
    for field, value in filter_fields.items():
        if value:
            qs = qs.filter(**{field: value})

    sort_col = request.GET.get("sort")
    sort_dir = request.GET.get("dir", "asc")
    if sort_col:
        qs = qs.order_by(f"-{sort_col}" if sort_dir == "desc" else sort_col)

    return qs

# 🖼️ Tek görseli tam ekranda görüntüleme
@login_required
def view_image(request, image_id):
    image = get_object_or_404(OrderImage, id=image_id)
    return render(request, "core/view_image.html", {"image": image})


# 📋 Sipariş Listeleme (Son Durum Gecikmesi Giderildi)
from django.db.models import OuterRef, Subquery, Q, Value, CharField
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.shortcuts import render
from core.models import Order, OrderEvent


from django.db import close_old_connections  # ⬅️ En üste import ekle

@never_cache
@login_required
def order_list(request):
    close_old_connections()

    # -----------------------------------------
    # 📌 1) TÜM SİPARİŞLERİ AL ve yeni/okunmamış hesapla
    # -----------------------------------------
    all_orders = Order.objects.only("id", "last_updated")

    # 📊 Tüm siparişlerin toplam adedi (filtre öncesi)
    total_count = Order.objects.count()


    seen_map = {
        s.order_id: s.seen_time
        for s in OrderSeen.objects.filter(user=request.user)
    }

    new_flags = {}
    for o in all_orders:
        last_seen = seen_map.get(o.id)
        if not last_seen:
            new_flags[o.id] = True
        else:
            new_flags[o.id] = o.last_updated > last_seen

    request.user.userprofile.last_seen_orders = timezone.now()
    request.user.userprofile.save(update_fields=["last_seen_orders"])

    # -----------------------------------------
    # 📌 2) TÜRKÇE DURUM SÖZLÜĞÜ
    # -----------------------------------------
    STAGE_TRANSLATIONS = {
    # --- Malzeme ---
    ("malzeme_durum", "kesildi"): "Malzemesi Kesildi",
    ("malzeme_durum", "boyandi"): "Malzemesi Boyandı",
    ("malzeme_durum", "eksik"): "Malzemesi Eksik",

    # --- Kesim ---
    ("kesim_durum", "siraya_alindi"): "Kesim Sırasına Alındı",
    ("kesim_durum", "basladi"): "Kesim Başladı",
    ("kesim_durum", "kismi"): "Kısmi Kesim yapıldı",
    ("kesim_durum", "bitti"): "Kesildi",

    # --- Dikim ---
    ("dikim_durum", "siraya_alindi"): "Dikim Sırasına Alındı",
    ("dikim_durum", "basladi"): "Dikim Başladı",
    ("dikim_durum", "kismi"): "Kısmi Dikim yapıldı",
    ("dikim_durum", "bitti"): "Dikildi",

    # --- Fason Dikim ---
    ("dikim_fason_durumu", "verildi"): "Fason Dikime Verildi",
    ("dikim_fason_durumu", "alindi"): "Fason Dikimden Alındı",

    # --- Nakış ---
    ("nakis_durum", "verildi"): "Nakışa Verildi",
    ("nakis_durum", "alindi"): "Nakıştan Alındı",

    # --- Süsleme ---
    ("susleme_durum", "siraya_alindi"): "Süsleme Sırasına Alındı",
    ("susleme_durum", "basladi"): "Süsleme Başladı",
    ("susleme_durum", "kismi"): "Kısmi Süsleme",
    ("susleme_durum", "bitti"): "Süslendi",

    # --- Fason Süsleme ---
    ("susleme_fason_durumu", "verildi"): "Fason Süslemeye Verildi",
    ("susleme_fason_durumu", "alindi"): "Fason Süslemeden Alındı",

    # --- Sevkiyat & Depo ---
    ("sevkiyat_durum", "gonderildi"): "Sevkedildi",
    ("sevkiyat_durum", "depoya"): "Depoya Girdi",
}


    # -----------------------------------------
    # 📌 3) EN SON EVENT
    # -----------------------------------------
    latest_event = (
    OrderEvent.objects
        .filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")  
        .exclude(stage__in=[
            "satis_fiyati",
            "ekstra_maliyet",
            "maliyet_override",
            "maliyet_uygulanan",
        ])
        .order_by("-timestamp", "-id")[:1]
)


    # -----------------------------------------
    # 📌 4) ANA QUERY
    # -----------------------------------------
    qs = (
        Order.objects.select_related("musteri")
        .annotate(
            latest_stage=Subquery(latest_event.values("stage")),
            latest_value=Subquery(latest_event.values("value")),
            last_status_date=Subquery(latest_event.values("timestamp"), output_field=DateTimeField()),
        )
        .order_by("-id")
    )


    qs_for_counts = qs  # <-- aktif/pasif/sevkedilen sayıları için referans queryset

    # -----------------------------------------
    # 📌 4.1) AKTİF / PASİF (GÖRÜNÜRLÜK) FİLTRESİ
    # -----------------------------------------
    active_values = request.GET.getlist("active")

    # Eğer hiçbir şey seçilmediyse varsayılan: aktifleri göster
    if not active_values:
        active_values = ["1"]

    # all seçildiyse veya hem 1 hem 0 seçildiyse -> filtre yok
    if "all" in active_values or ("1" in active_values and "0" in active_values):
        pass
    elif "1" in active_values:
        qs = qs.filter(is_active=True)
    elif "0" in active_values:
        qs = qs.filter(is_active=False)





    # -----------------------------------------
    # 📌 5) FİLTRELER (DOĞRU HALİ)
    # -----------------------------------------
    siparis_nolar = request.GET.getlist("siparis_no")
    musteriler = request.GET.getlist("musteri")
    urun_kodlari = request.GET.getlist("urun_kodu")
    renkler = request.GET.getlist("renk")
    bedenler = request.GET.getlist("beden")
    status_filter = request.GET.getlist("status")
    siparis_tipleri = request.GET.getlist("siparis_tipi")
    musteri_referans_list = request.GET.getlist("musteri_referans")

    # --- Filtre Uygulama ---
    if siparis_nolar:
        qs = qs.filter(siparis_numarasi__in=siparis_nolar)

    if musteriler:
        qs = qs.filter(musteri__ad__in=musteriler)

    if urun_kodlari:
        qs = qs.filter(urun_kodu__in=urun_kodlari)

    if renkler:
        qs = qs.filter(renk__in=renkler)

    if bedenler:
        qs = qs.filter(beden__in=bedenler)

    if siparis_tipleri:
        qs = qs.filter(siparis_tipi__in=siparis_tipleri)

    if musteri_referans_list:
        qs = qs.filter(musteri_referans__in=musteri_referans_list)

    # --- Durum Filtresi ---
    if status_filter:
        stage_value_pairs = [
            key for key, val in STAGE_TRANSLATIONS.items()
            if val in status_filter
        ]
        q = Q()
        for stage, value in stage_value_pairs:
            q |= Q(latest_stage=stage, latest_value=value)
        qs = qs.filter(q)

    # --- Teslim Tarihi Aralığı ---
    teslim_baslangic = request.GET.get("teslim_tarihi_baslangic")
    teslim_bitis = request.GET.get("teslim_tarihi_bitis")

    if teslim_baslangic and teslim_bitis:
        qs = qs.filter(teslim_tarihi__range=[teslim_baslangic, teslim_bitis])
    elif teslim_baslangic:
        qs = qs.filter(teslim_tarihi__gte=teslim_baslangic)
    elif teslim_bitis:
        qs = qs.filter(teslim_tarihi__lte=teslim_bitis)

    # ✅ Aktif / Pasif / Sevkedilen sayılarını hesapla
    aktif_count = qs_for_counts.filter(is_active=True).count()
    pasif_count = qs_for_counts.filter(is_active=False).count()

    # ✅ Sevkedilen = SADECE aktif + sevkiyat gönderildi olanlar
    sevke_count = qs_for_counts.filter(
        is_active=True,
        latest_stage="sevkiyat_durum",
        latest_value="gonderildi"
    ).count()


    # 📊 Filtrelenmiş sipariş adedi
    filtered_count = qs.count()

    # -----------------------------------------
    # 📌 TEMPLATE İÇİN SEÇİLEN DEĞERLER
    # -----------------------------------------
    selected_siparis_no = siparis_nolar
    selected_musteri = musteriler
    selected_urun_kodu = urun_kodlari
    selected_renk = renkler
    selected_beden = bedenler
    selected_status = status_filter
    selected_siparis_tipi = siparis_tipleri
    selected_musteri_referans = musteri_referans_list


        # -----------------------------------------
    # 🟦 6) SAYFALAMA
    # -----------------------------------------
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    # -----------------------------------------
    # 🟦 7) SON DURUM HESAPLAMA
    # -----------------------------------------
    finance_fields = [
        "satis_fiyati",
        "ekstra_maliyet",
        "maliyet_override",
        "maliyet_uygulanan",
    ]

    for order in page_obj:
        order.is_new = new_flags.get(order.id, False)

        # Finansal alanlar son durumu bozmasın
        if order.latest_stage in finance_fields:
            order.formatted_status = order.son_durum
            continue

        if not order.latest_stage or not order.latest_value:
            order.formatted_status = "-"
            continue

        stage = normalize(order.latest_stage)
        value = normalize(order.latest_value)

        key = (stage, value)

        if key in STAGE_TRANSLATIONS:
            order.formatted_status = STAGE_TRANSLATIONS[key]
            continue

        nice_stage = (
            order.latest_stage.replace("_durum", "")
            .replace("_fason_durumu", " Fason")
            .replace("_", " ")
            .title()
        )
        nice_value = order.latest_value.replace("_", " ").title()

        order.formatted_status = f"{nice_stage} → {nice_value}"

    # -----------------------------------------
    # 📌 8) CONTEXT (⚠️ Döngü dışı olmalı)
    # -----------------------------------------
    is_manager = request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    context = {
        "orders": page_obj,
        "siparis_options": Order.objects.values_list("siparis_numarasi", flat=True).distinct().order_by("siparis_numarasi"),
        "musteri_options": Order.objects.values_list("musteri__ad", flat=True).distinct().order_by("musteri__ad"),
        "urun_options": Order.objects.values_list("urun_kodu", flat=True).distinct().order_by("urun_kodu"),
        "renk_options": Order.objects.values_list("renk", flat=True).distinct().order_by("renk"),
        "beden_options": Order.objects.values_list("beden", flat=True).distinct().order_by("beden"),
        "musteri_referans_options": Order.objects.exclude(musteri_referans__isnull=True)
                                                .exclude(musteri_referans__exact="")
                                                .values_list("musteri_referans", flat=True)
                                                .distinct()
                                                .order_by("musteri_referans"),

        "status_options": sorted(set(STAGE_TRANSLATIONS.values())),
        "siparis_tipi_options": Order.objects.values_list("siparis_tipi", flat=True).distinct().order_by("siparis_tipi"),
        "total_count": total_count,
        "filtered_count": filtered_count,
        "aktif_count": aktif_count,
        "pasif_count": pasif_count,
        "sevke_count": sevke_count,
        "is_manager": is_manager,
        "request": request, 
    }

    response = render(request, "core/order_list.html", context)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response   # ⚠️ Fonksiyonun tam sonu


@login_required
@never_cache
def order_create(request):
    if request.method == "POST":
        form = OrderForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)

            urun_kodu = form.cleaned_data.get("urun_kodu")
            if urun_kodu:
                try:
                    from .models import ProductCost
                    maliyet_obj = ProductCost.objects.get(urun_kodu=urun_kodu)
                    order.maliyet_uygulanan = maliyet_obj.maliyet
                    order.maliyet_para_birimi = maliyet_obj.para_birimi
                except ProductCost.DoesNotExist:
                    order.maliyet_uygulanan = None

            order.save()                 # 1️⃣ Siparişi kaydet
            cache.clear()                # 3️⃣ Cache temizle

            return redirect(
                f"{reverse('order_list')}?t={int(time.time())}"
            )
    else:
        form = OrderForm(user=request.user)

    is_manager = request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    aktif_musteriler = Musteri.objects.filter(aktif=True).order_by("ad")

    return render(request, "core/order_form.html", {
        "form": form,
        "is_manager": is_manager,
        "aktif_musteriler": aktif_musteriler,
    })



# 👤 Yeni Müşteri
@login_required
def musteri_create(request):
    if request.method == "POST":
        form = MusteriForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("order_create")
    else:
        form = MusteriForm()
    return render(request, "core/musteri_form.html", {"form": form})


# 🧠 Müşteri arama (autocomplete)
@login_required
def musteri_search(request):
    term = request.GET.get("term", "")
    qs = Musteri.objects.filter(ad__icontains=term).values_list("ad", flat=True)[:20]
    return JsonResponse(list(qs), safe=False)


@login_required
@never_cache
def order_detail(request, pk):
    # 📌 Önce siparişi çek
    order = get_object_or_404(Order.objects.select_related("musteri"), pk=pk)

    # 👁️ Kullanıcı bu siparişi gördü olarak işaretle
    OrderSeen.objects.update_or_create(
        user=request.user,
        order=order,
        defaults={"seen_time": timezone.now()}
    )

    # 📌 Diğer veriler
    nakisciler = Nakisci.objects.all()
    fasoncular = Fasoncu.objects.all()

    # 🔹 Üretim event'leri
    events = OrderEvent.objects.filter(order=order).order_by("-timestamp")
    update_events = events.filter(event_type="order_update")

    # Silme sonrası ekranda, geçmişte gerçekten kalan son aşamayı göster.
    from .services.order_status import latest_status_event, status_label
    current_status = status_label(latest_status_event(order))

    # 🔒 Personel fiyat değişikliklerini görmesin
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        gizli_alanlar = [
            "satis_fiyati",
            "ekstra_maliyet",
            "maliyet_override",
            "maliyet_uygulanan",
        ]
        events = events.exclude(stage__in=gizli_alanlar)
        update_events = update_events.exclude(stage__in=gizli_alanlar)

    # 🔥 Depo / Hazırdan Verilen Ürün Hareketleri
    uretim_kayitlari = UretimGecmisi.objects.filter(order=order).order_by("-tarih")

    is_manager = request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    # 📌 Geri dönüş URL'si (liste, rapor veya QR için akıllı sistem)
    return_url = request.GET.get("return_url")  # 1) URL’de varsa kullan

    # 2) Yoksa (ör. QR’dan geldiyse), HTTP_REFERER'i dene
    if not return_url:
        return_url = request.META.get("HTTP_REFERER")

    # 3) Yine yoksa (tarayıcı geçmişi yoksa), güvenli fallback → order list
    if not return_url:
        return_url = "/orders/"


    return render(
        request,
        "core/order_detail.html",
        {
            "order": order,
            "nakisciler": nakisciler,
            "fasoncular": fasoncular,
            "events": events,
            "update_events": update_events,
            "is_manager": is_manager,
            "uretim_kayitlari": uretim_kayitlari,
            "back_url": return_url,
            "current_status": current_status,
        },
    )





@login_required
def depo_ozet(request):
    depo_ozetleri = (
        DepoStok.objects
        .values('depo')
        .annotate(
            toplam_adet=Sum('adet'),
            kayit_sayisi=Count('id'),
            son_guncelleme=Max('eklenme_tarihi')  # ✅ düzeltildi
        )
        .order_by('depo')
    )

    return render(request, 'depolar/ozet.html', {'depolar': depo_ozetleri})

# 🔐 Özel Login (hızlı ve güvenli)
from django.shortcuts import redirect

@csrf_exempt
def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            next_url = request.GET.get("next") or "/"
            return redirect(next_url)   # ✅ BUNU EKLE

        return render(request, "registration/custom_login.html", {"error": True})

    return render(request, "registration/custom_login.html")




@login_required
def update_stage(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # Stage ve value (POST>GET)
    stage = request.POST.get("stage") or request.GET.get("stage")
    value = request.POST.get("value") or request.GET.get("value")

    # Ek alanlar
    aciklama = request.POST.get("aciklama") or request.GET.get("aciklama")
    fasoncu_id = request.POST.get("fasoncu") or request.GET.get("fasoncu")
    nakisci_id = request.POST.get("nakisci") or request.GET.get("nakisci")

    if not stage or not value:
        return HttpResponseForbidden("Eksik veri")

    # ---------------------------------------------------------
    # 1) ORDER ÜZERİNDE AŞAMA GÜNCELLE
    # ---------------------------------------------------------
    # Bazı aşamalar (ör. malzeme) yalnızca işlem geçmişinde tutulur.
    # Order modelinde gerçek bir alan varsa ayrıca o alanı güncelle.
    order_field_names = {field.name for field in order._meta.concrete_fields}
    try:
        if stage not in order_field_names:
            raise AttributeError
        setattr(order, stage, value)
        order.save(update_fields=[stage])
    except AttributeError:
        pass
    except Exception as e:
        print("Aşama güncelleme hatası:", e)

    # ---------------------------------------------------------
    # 2) ORDER EVENT OLUŞTUR
    # ---------------------------------------------------------
    event = OrderEvent.objects.create(
        order=order,
        user=request.user.username,
        stage=stage,
        value=value,
        aciklama=aciklama or None,
        event_type="stage",
        adet=order.adet or 1,
    )

    # Fasoncu eklenmişse
    if fasoncu_id:
        try:
            event.fasoncu_id = fasoncu_id
            event.save()
        except:
            pass

    # Nakışçı eklenmişse
    if nakisci_id:
        try:
            event.nakisci_id = nakisci_id
            event.save()
        except:
            pass

    # ---------------------------------------------------------
    # 3) HTMX İSTEĞİ → SADECE PANELİ DÖNDÜR
    # ---------------------------------------------------------
    if request.headers.get("HX-Request"):
        return render(request, "core/_uretim_paneli.html", {
            "order": order,
            "events": OrderEvent.objects.filter(order=order).order_by("-timestamp"),
            "fasoncular": Fasoncu.objects.all(),
            "nakisciler": Nakisci.objects.all(),
            "is_manager": request.user.groups.filter(name__in=["patron", "mudur"]).exists(),
        })

    # Normal istek → JSON
    return JsonResponse({"status": "ok"})




# ✅ Ürün resmi yüklemek / değiştirmek için fonksiyon
@login_required
def order_upload_image(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST" and request.FILES.get("resim"):
        order.resim = request.FILES["resim"]
        order.save()

    return redirect("order_detail", pk=order.pk)

@login_required
@never_cache
def order_edit(request, pk):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    order = get_object_or_404(Order, pk=pk)

    # 🛡️ Yetki kontrolü
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    # 📌 Güncellemeden önce eski hali sakla
    old_data = {
        "musteri": str(order.musteri) if order.musteri else None,
        "siparis_tipi": order.siparis_tipi,
        "urun_kodu": order.urun_kodu,
        "renk": order.renk,
        "beden": order.beden,
        "adet": order.adet,
        "aciklama": order.aciklama,
        "musteri_referans": order.musteri_referans,
        "teslim_tarihi": order.teslim_tarihi,
        "satis_fiyati": order.satis_fiyati,
        "ekstra_maliyet": order.ekstra_maliyet,
        "maliyet_override": order.maliyet_override,
    }

    if request.method == "POST":
        form = OrderForm(request.POST, request.FILES, instance=order, user=request.user)

        if form.is_valid():
            updated_order = form.save()
            updated_order.refresh_from_db()   # 🔥 Değişiklikleri anında getir

            # ------------------------------------------------------------
            # 🔥 KAR / MALİYET / FİYAT HESAPLAMASINI ANINDA TETİKLE
            # ------------------------------------------------------------
            _ = updated_order.efektif_maliyet
            _ = updated_order.toplam_maliyet
            _ = updated_order.kar_backend
            _ = updated_order.kar     # (frontend property)

            # ------------------------------------------------------------
            # 🔥 DEĞİŞİKLİK TESPİTİ
            # ------------------------------------------------------------
            new_data = {
                "musteri": str(updated_order.musteri) if updated_order.musteri else None,
                "siparis_tipi": updated_order.siparis_tipi,
                "urun_kodu": updated_order.urun_kodu,
                "renk": updated_order.renk,
                "beden": updated_order.beden,
                "adet": updated_order.adet,
                "aciklama": updated_order.aciklama,
                "musteri_referans": updated_order.musteri_referans,
                "teslim_tarihi": updated_order.teslim_tarihi,
                "satis_fiyati": updated_order.satis_fiyati,
                "ekstra_maliyet": updated_order.ekstra_maliyet,
                "maliyet_override": updated_order.maliyet_override,
            }

            changed_fields = []

            for field, old_value in old_data.items():
                new_value = new_data[field]
                if str(old_value) != str(new_value):
                    changed_fields.append(field)

                    # 🔥 Güncelleme logu
                    OrderEvent.objects.create(
                        order=updated_order,
                        user=request.user.username,
                        gorev="yok",
                        stage=field,
                        value=f"{field} değişti",
                        event_type="order_update",
                        old_value=str(old_value),
                        new_value=str(new_value),
                    )

            # ------------------------------------------------------------
            # 🔔 BİLDİRİM GÖNDER (eğer değişiklik varsa)
            # ------------------------------------------------------------
            if changed_fields:
                from .models import Notification

                alan_etiketleri = {
                    "musteri": "Müşteri",
                    "siparis_tipi": "Sipariş Tipi",
                    "urun_kodu": "Ürün Kodu",
                    "renk": "Renk",
                    "beden": "Beden",
                    "adet": "Adet",
                    "aciklama": "Açıklama",
                    "musteri_referans": "Müşteri Ref",
                    "teslim_tarihi": "Teslim Tarihi",
                    "satis_fiyati": "Satış Fiyatı",
                    "ekstra_maliyet": "Ekstra Maliyet",
                    "maliyet_override": "Manuel Maliyet",
                }

                okunur_alanlar = [alan_etiketleri.get(f, f) for f in changed_fields]
                degisen_text = ", ".join(okunur_alanlar)

                title = f"{updated_order.siparis_numarasi} güncellendi"
                message = f"Değişen alanlar: {degisen_text}. Güncelleyen: {request.user.username}"

                notif_list = [
                    Notification(
                        user=u,
                        order=updated_order,
                        title=title,
                        message=message,
                    )
                    for u in User.objects.all()
                ]

                Notification.objects.bulk_create(notif_list)

            # ------------------------------------------------------------
            # 🚀 CACHE TEMİZLE – KESİN GEREKİYOR!!!
            # ------------------------------------------------------------
            from django.core.cache import cache
            cache.clear()

            # ------------------------------------------------------------
            # 🚀 Sayfayı yenileyerek sonucunu göster
            # ------------------------------------------------------------
            return redirect(f"{reverse('order_detail', args=[pk])}?t={int(time.time())}")

    else:
        form = OrderForm(instance=order, user=request.user)

    is_manager = request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    return render(request, "core/order_form.html", {
        "form": form,
        "order": order,
        "edit_mode": True,
        "is_manager": is_manager,
    })








@login_required
def order_add_image(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # 🛡️ Yalnızca patron veya müdür yükleme yapabilir
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    if request.method == "POST":
        images = request.FILES.getlist("images")
        if not images:
            messages.warning(request, "Herhangi bir dosya seçilmedi.")
            return redirect("order_detail", pk=pk)

        for file in images:
            try:
                OrderImage.objects.create(order=order, image=file)
            except Exception as e:
                print("⚠️ Görsel yükleme hatası:", e)
                messages.error(request, f"{file.name} yüklenemedi: {e}")

        messages.success(request, f"{len(images)} görsel başarıyla yüklendi ✅")
        return redirect("order_detail", pk=pk)

    return HttpResponseForbidden("Geçersiz istek yöntemi.")

@login_required
def delete_order_image(request, image_id):
    # 🛡️ Sadece patron veya müdür silebilir
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    image = get_object_or_404(OrderImage, id=image_id)
    order_id = image.order.id

    # 🧹 Supabase tarafında da silmeyi istiyorsan (opsiyonel)
    try:
        from django.conf import settings
        from supabase import create_client
        import os

        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        filename = os.path.basename(image.image_url or "")
        if filename:
            supabase.storage.from_(settings.SUPABASE_BUCKET_NAME).remove([filename])
    except Exception as e:
        print("⚠️ Supabase silme hatası:", e)

    # 🔸 Veritabanından kaydı sil
    image.delete()
    messages.success(request, "Görsel başarıyla silindi.")
    return redirect("order_detail", pk=order_id)


@login_required
def delete_order_event(request, event_id):
    event = get_object_or_404(OrderEvent, id=event_id)

    # 🛡️ Sadece patron veya müdür silebilir
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu işlemi yapma yetkiniz yok.")

    order = event.order
    order_id = order.id
    deleted_stage = event.stage if event.event_type == "stage" else None
    event.delete()

    if deleted_stage:
        from .services.order_status import sync_order_stage_from_events

        sync_order_stage_from_events(order, deleted_stage)

    cache.clear()

    messages.success(request, "Üretim geçmişi kaydı silindi.")
    return redirect("order_detail", pk=order_id)


@login_required
@csrf_exempt
def order_delete(request, pk):

    # 🛡️ YETKİ KONTROLÜ
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return JsonResponse({"status": "error", "message": "Yetki yok"}, status=403)

    # 🛠️ SİLME
    if request.method == "POST":
        order = get_object_or_404(Order, pk=pk)
        order.delete()
        return JsonResponse({"status": "ok"}, status=200)

    return JsonResponse({"status": "error", "message": "POST gerekli"}, status=405)



# 📊 GENEL ÜRETİM RAPORU
@login_required
def reports_view(request):
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")
    gorev_filter = request.GET.get("gorev")

    events = OrderEvent.objects.select_related("order").all()

    if start_date:
        events = events.filter(timestamp__date__gte=start_date)
    if end_date:
        events = events.filter(timestamp__date__lte=end_date)
    if gorev_filter:
        events = events.filter(gorev=gorev_filter)

    stage_summary = (
        events.values("stage", "value")
        .annotate(count=Count("id"))
        .order_by("stage")
    )

    user_summary = (
        events.values("user", "gorev")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    context = {
        "stage_summary": stage_summary,
        "user_summary": user_summary,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "gorev_filter": gorev_filter or "",
        "GOREVLER": UserProfile.GOREV_SECENEKLERI,
    }

    return render(request, "reports/general_reports.html", context)


# 📦 GİDEN ÜRÜNLER RAPORU (yeni versiyon)
@login_required
def giden_urunler_raporu(request):
    # Sadece patron veya müdür görebilir
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu raporu görme yetkiniz yok.")

    orders = list(
    Order.objects
    .filter(sevkiyat_durum="gonderildi")
    .select_related("musteri")
    .order_by("-id")
)


    # Toplam kar hesaplama
    toplam_kar = sum([o.kar or 0 for o in orders if o.kar is not None])
    toplam_satis = sum([o.satis_fiyati or 0 for o in orders if o.satis_fiyati is not None])
    toplam_maliyet = sum([o.efektif_maliyet or 0 for o in orders if o.efektif_maliyet is not None])

    context = {
        "orders": orders,
        "toplam_kar": toplam_kar,
        "toplam_satis": toplam_satis,
        "toplam_maliyet": toplam_maliyet,
    }

    return render(request, "reports/giden_urunler.html", context)


# 👥 Kullanıcı Yönetimi
@login_required
def user_management_view(request):
    # 🛡️ Sadece patron ve müdür erişebilsin
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
        
    from django.contrib import messages
    from django.contrib.auth.models import Group, User

    users = User.objects.all().order_by("username")
    profiles = {p.user_id: p for p in UserProfile.objects.filter(user__in=users)}

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "create_user":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "").strip()
            role = request.POST.get("role", "").strip()
            gorev = request.POST.get("gorev", "yok").strip()

            if not username or not password or not role:
                messages.error(request, "Kullanıcı adı, şifre ve rol zorunludur.")
                return redirect("user_management")

            if User.objects.filter(username=username).exists():
                messages.warning(request, f"{username} zaten mevcut ⏸️")
                return redirect("user_management")

            user = User.objects.create_user(username=username, password=password)
            if role in ["personel", "mudur", "patron"]:
                group, _ = Group.objects.get_or_create(name=role)
                user.groups.add(group)

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.gorev = gorev
            profile.save()

            messages.success(request, f"{username} eklendi ✅")
            return redirect("user_management")

        elif action == "reset_password":
            user_id = request.POST.get("user_id")
            new_password = request.POST.get("new_password", "").strip()
            try:
                u = User.objects.get(pk=user_id)
                if not new_password:
                    messages.error(request, "Yeni şifre boş olamaz.")
                else:
                    u.set_password(new_password)
                    u.save()
                    messages.success(request, f"{u.username} için şifre güncellendi 🔐")
            except User.DoesNotExist:
                messages.error(request, "Kullanıcı bulunamadı.")
            return redirect("user_management")

        elif action == "update_gorev":
            user_id = request.POST.get("user_id")
            gorev = request.POST.get("gorev", "yok").strip()
            try:
                u = User.objects.get(pk=user_id)
                profile, _ = UserProfile.objects.get_or_create(user=u)
                profile.gorev = gorev
                profile.save()
                messages.success(request, f"{u.username} görevi '{profile.gorev}' olarak güncellendi 🏷️")
            except User.DoesNotExist:
                messages.error(request, "Kullanıcı bulunamadı.")
            return redirect("user_management")

        elif action == "delete_user":
            user_id = request.POST.get("user_id")
            try:
                u = User.objects.get(pk=user_id)
                if u == request.user:
                    messages.warning(request, "Kendinizi silemezsiniz.")
                else:
                    u.delete()
                    messages.success(request, "Kullanıcı silindi 🗑️")
            except User.DoesNotExist:
                messages.error(request, "Silinecek kullanıcı bulunamadı.")
            return redirect("user_management")

    context = {
        "users": users,
        "profiles": profiles,
        "GOREVLER": UserProfile.GOREV_SECENEKLERI,
    }
    return render(request, "user_management.html", context)


@login_required
def staff_reports_view(request):
    users = User.objects.all()
    selected_user = request.GET.get("user")
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    events = []

    # Sadece filtreleme yapılmışsa verileri getir
    if selected_user and start_date and end_date:
        try:
            user = User.objects.get(username=selected_user)
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

            events = (
                OrderEvent.objects.filter(
                    user=user,
                    timestamp__range=[start, end]
                )
                .select_related("order", "order__musteri")
                .order_by("-timestamp")
            )
        except User.DoesNotExist:
            pass

    context = {
        "users": users,
        "events": events,
        "selected_user": selected_user,
        "start_date": start_date,
        "end_date": end_date,
    }
    return render(request, "reports/staff_reports.html", context)



from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from core.models import Order

from decimal import Decimal
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce


# 🧾 ÜRÜN MALİYET LİSTESİ YÖNETİMİ
@login_required
def product_cost_list(request):
    # Sadece patron veya müdür erişebilir
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    # 🧩 Yeni kayıt ekleme veya silme işlemleri
    if request.method == "POST":
        action = request.POST.get("action")

        # ➕ Yeni kayıt ekle veya güncelle
        if action == "add":
            urun_kodu = request.POST.get("urun_kodu", "").strip().upper()
            maliyet = request.POST.get("maliyet", "").strip()
            para_birimi = request.POST.get("para_birimi", "TRY")

            if urun_kodu and maliyet:
                ProductCost.objects.update_or_create(
                    urun_kodu=urun_kodu,
                    defaults={"maliyet": maliyet, "para_birimi": para_birimi},
                )

        # ❌ Silme işlemi
        elif action == "delete":
            pk = request.POST.get("id")
            ProductCost.objects.filter(id=pk).delete()

    # 📋 Listele (sayfalama ile)
    maliyetler = ProductCost.objects.all().order_by("urun_kodu")
    paginator = Paginator(maliyetler, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "core/product_cost_list.html", {"costs": page_obj})



# 📊 RAPORLAR ANA SAYFASI (Raporlara Git →)
@login_required
def reports_home(request):
    # Sadece patron veya müdür görebilsin
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    
    # reports/reports_home.html şablonunu render et
    return render(request, "reports/reports_home.html")

# 💬 Asistan sayfası (HTML)
@login_required
def ai_assistant_view(request):
    return render(request, "core/asistan.html")


@csrf_exempt
def ai_assistant_api(request):
    if request.method == "POST":
        try:
            import requests, os, json
            data = json.loads(request.body)
            user_message = data.get("message", "").strip()

            if not user_message:
                return JsonResponse({"reply": "❗Lütfen bir mesaj yazın."})

            GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)
            if not GEMINI_API_KEY:
                return JsonResponse({"reply": "🔧 Asistan çevrimdışı (API anahtarı eksik)."})

            # ✅ Güncel model ve doğru endpoint
            MODEL = "gemini-2.5-flash"  # istersen gemini-2.5-pro ile değiştir
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

            payload = {
                "contents": [
                    {"parts": [{"text": user_message}]}
                ]
            }
            headers = {"Content-Type": "application/json"}

            response = requests.post(url, headers=headers, json=payload, timeout=30)
            result = response.json()

            if "candidates" in result and len(result["candidates"]) > 0:
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
            elif "error" in result:
                reply = f"⚠️ API Hatası: {result['error'].get('message', 'Bilinmeyen hata')}"
            else:
                reply = f"⚠️ Beklenmeyen yanıt: {result}"

        except Exception as e:
            reply = f"⚠️ Bir hata oluştu: {str(e)}"

        return JsonResponse({"reply": reply})

    # GET isteklerine basit bir yanıt dön
    return JsonResponse({"reply": "Bu endpoint sadece POST isteklerini kabul eder."})

@login_required
def fasoncu_ekle(request):
    if request.method == "POST":
        ad = request.POST.get("ad")
        telefon = request.POST.get("telefon")
        notlar = request.POST.get("notlar")

        if ad:
            Fasoncu.objects.create(ad=ad, telefon=telefon, notlar=notlar)
            messages.success(request, f"{ad} başarıyla eklendi.")
            return redirect("/reports/fasoncu/")
        else:
            messages.error(request, "Fasoncu adı boş bırakılamaz.")
    return render(request, "fasoncu_ekle.html")

@login_required
def fasoncu_raporu(request):
    from django.db.models import Q

    # 🔹 Tüm fasoncuları filtre dropdown için al
    fasoncular = Fasoncu.objects.all().order_by("ad")

    # 🔹 Seçili fasoncu ve tarih aralıklarını al
    fasoncu_id = request.GET.get("fasoncu")
    t1 = request.GET.get("t1")
    t2 = request.GET.get("t2")

    # 🔹 OrderEvent’lerden filtreye göre çekim
    raporlar = OrderEvent.objects.select_related("order", "order__musteri", "fasoncu")

    # Eğer belirli fasoncu seçildiyse
    if fasoncu_id:
        raporlar = raporlar.filter(fasoncu_id=fasoncu_id)

    # Eğer tarih aralığı varsa uygula
    if t1 and t2:
        raporlar = raporlar.filter(timestamp__range=[t1, t2])
    elif t1:
        raporlar = raporlar.filter(timestamp__date__gte=t1)
    elif t2:
        raporlar = raporlar.filter(timestamp__date__lte=t2)

    # 🔹 Yalnızca fasonla ilgili event'leri göster (örnek: fasona verildi / alındı)
    raporlar = raporlar.filter(
        Q(stage__icontains="fason")  # "dikim_fason_durumu" veya "susleme_fason_durumu"
    ).order_by("-timestamp")

    # 🔹 Görsel veriler için küçük context hazırlama
    data = []
    for r in raporlar:
        data.append({
            "order": r.order,
            "durum": f"{r.stage.replace('_', ' ').title()} → {r.value.title()}",
            "tarih": r.timestamp,
            "personel": r.user,
        })

    context = {
        "fasoncular": fasoncular,
        "raporlar": data,
    }
    return render(request, "reports/fasoncu_raporu.html", context)

@login_required
def fasoncu_yeni(request):
    if request.method == "POST":
        ad = request.POST.get("ad")
        telefon = request.POST.get("telefon")
        notlar = request.POST.get("notlar")

        if ad:
            Fasoncu.objects.create(ad=ad, telefon=telefon, notlar=notlar, eklenme_tarihi=timezone.now())
            messages.success(request, "Yeni fasoncu başarıyla eklendi.")
            return redirect("/reports/fasoncu/")
        else:
            messages.error(request, "Fasoncu adı zorunludur.")

    return render(request, "fasoncu_yeni.html")



@login_required
def nakisci_raporu(request):
    from django.db.models import Q

    # 🔹 Tüm nakışçıları filtre dropdown için al
    nakiscilar = Nakisci.objects.all().order_by("ad")

    # 🔹 Seçili nakışçı ve tarih aralıklarını al
    nakisci_id = request.GET.get("nakisci")
    t1 = request.GET.get("t1")
    t2 = request.GET.get("t2")

    # 🔹 OrderEvent’lerden filtreye göre çekim
    raporlar = OrderEvent.objects.select_related("order", "order__musteri", "nakisci")

    # Eğer belirli nakışçı seçildiyse
    if nakisci_id:
        raporlar = raporlar.filter(nakisci_id=nakisci_id)

    # Eğer tarih aralığı varsa uygula
    if t1 and t2:
        raporlar = raporlar.filter(timestamp__range=[t1, t2])
    elif t1:
        raporlar = raporlar.filter(timestamp__date__gte=t1)
    elif t2:
        raporlar = raporlar.filter(timestamp__date__lte=t2)

    # 🔹 Yalnızca nakış ile ilgili event’leri göster (örnek: nakışa verildi / alındı)
    raporlar = raporlar.filter(
        Q(stage__icontains="nakis") | Q(stage__icontains="nakış")
    ).order_by("-timestamp")

    # 🔹 Görsel veriler için context hazırlama
    data = []
    for r in raporlar:
        data.append({
            "order": r.order,
            "durum": f"{r.stage.replace('_', ' ').title()} → {r.value.title()}",
            "tarih": r.timestamp,
            "personel": r.user,
        })

    context = {
        "nakiscilar": nakiscilar,
        "raporlar": data,
    }
    return render(request, "reports/nakisci_raporu.html", context)




@login_required
def nakisci_ekle(request):
    if request.method == 'POST':
        ad = request.POST.get('ad', '').strip()
        telefon = request.POST.get('telefon', '').strip()
        notlar = request.POST.get('notlar', '').strip()
        if ad:
            Nakisci.objects.create(ad=ad, telefon=telefon, notlar=notlar)
            return redirect('nakisci_raporu')  # veya '/reports/nakisci/'
    return render(request, 'nakisci/yeni.html')

from django.db.models import F, Sum

@login_required
def depo_detay(request, depo_adi):

    stoklar = (
        DepoStok.objects
        .filter(depo=depo_adi)
        .select_related("order")
        .annotate(
            order_siparis_no=F("order__siparis_numarasi"),
            order_tipi=F("order__siparis_tipi"),
            order_musteri=F("order__musteri"),
            order_siparis_tarihi=F("order__siparis_tarihi"),
            order_teslim_tarihi=F("order__teslim_tarihi"),
        )
        .order_by("-eklenme_tarihi")
    )

    toplam_adet = stoklar.aggregate(Sum("adet"))["adet__sum"] or 0
    siparisler = Order.objects.all().order_by("-siparis_tarihi")

    return render(request, "depolar/detay.html", {
        "depo_adi": depo_adi,
        "stoklar": stoklar,
        "toplam_adet": toplam_adet,
        "siparisler": siparisler,
    })









@login_required
def depo_arama(request):
    # 🔍 Filtre parametreleri
    urun_kodu = request.GET.get("urun_kodu", "").strip()
    renk = request.GET.get("renk", "")
    beden = request.GET.get("beden", "")
    depo = request.GET.get("depo", "")

    # 🧮 Filtre oluştur
    filtre = Q()
    if urun_kodu:
        filtre &= Q(urun_kodu__icontains=urun_kodu)
    if renk:
        filtre &= Q(renk=renk)
    if beden:
        filtre &= Q(beden=beden)
    if depo:
        filtre &= Q(depo=depo)

    # 📦 Sorgu
    stoklar = []
    if any([urun_kodu, renk, beden, depo]):
        stoklar = (
            DepoStok.objects
            .filter(filtre)
            .select_related("order")  # 🔗 Sipariş ilişkisini getir
            .values(
                "depo",
                "urun_kodu",
                "renk",
                "beden",
                "order__id",
                "order__siparis_numarasi"
            )
            .annotate(toplam_adet=Sum("adet"))
            .order_by("depo", "urun_kodu")
        )

    # 🔽 Dropdown listeleri dinamik olarak çek
    renk_listesi = (
        DepoStok.objects.exclude(renk__isnull=True)
        .values_list("renk", flat=True).distinct().order_by("renk")
    )
    beden_listesi = (
        DepoStok.objects.exclude(beden__isnull=True)
        .values_list("beden", flat=True).distinct().order_by("beden")
    )
    depo_listesi = (
        DepoStok.objects.exclude(depo__isnull=True)
        .values_list("depo", flat=True).distinct().order_by("depo")
    )
    urun_listesi = (
        DepoStok.objects.exclude(urun_kodu__isnull=True)
        .values_list("urun_kodu", flat=True).distinct().order_by("urun_kodu")
    )

    context = {
        "stoklar": stoklar,
        "renk_listesi": renk_listesi,
        "beden_listesi": beden_listesi,
        "depo_listesi": depo_listesi,
        "urun_listesi": urun_listesi,
        "request": request,
    }
    return render(request, "depolar/arama.html", context)



@login_required
def hazirdan_ver(request, stok_id):
    stok = get_object_or_404(DepoStok, id=stok_id)

    if request.method == "POST":
        order_id = request.POST.get("order_id")
        hedef_order = get_object_or_404(Order, id=order_id)

        # 🔻 Stoktan 1 adet düş
        stok.adet = max(0, stok.adet - 1)

        # 🔻 STOĞA ÜRETİM siparişi (kaynak sipariş)
        kaynak_order = stok.order  

        # 🔻 Ürünü hedef siparişe aktar
        stok.order = hedef_order
        stok.save()

        # 🔹 Aynı siparişe ait önceki stok kayıtlarını temizle
        DepoStok.objects.filter(order=hedef_order).exclude(id=stok.id).delete()

        # ============================================================
        # 1) Kaynak sipariş için üretim geçmişi kaydı
        # ============================================================
        if kaynak_order:
            UretimGecmisi.objects.create(
                order=kaynak_order,
                urun=stok.urun_kodu,
                asama="Hazırdan Verildi",
                aciklama=f"Bu ürün {hedef_order.siparis_numarasi} siparişine gönderildi.",
            )

            # 🔥 OrderEvent (Order Detail'de görünmesi için)
            OrderEvent.objects.create(
                order=kaynak_order,
                user=request.user.username,
                gorev="hazir",
                stage="Hazırdan Verildi",
                value=f"{stok.urun_kodu} → {hedef_order.siparis_numarasi}",
                adet=1,
                event_type="stage",
            )

        # ============================================================
        # 2) Hedef sipariş için üretim geçmişi kaydı
        # ============================================================
        UretimGecmisi.objects.create(
            order=hedef_order,
            urun=stok.urun_kodu,
            asama="Depodan Teslim Alındı",
            aciklama=f"Bu ürün depodan alındı. Kaynak Sipariş: {kaynak_order.siparis_numarasi if kaynak_order else '-'}",
        )

        # 🔥 OrderEvent (Order Detail'de görünmesi için)
        OrderEvent.objects.create(
            order=hedef_order,
            user=request.user.username,
            gorev="hazir",
            stage="Depodan Teslim Alındı",
            value=stok.urun_kodu,
            adet=1,
            event_type="stage",
        )

        # ✔️ Kullanıcıya bildirim
        messages.success(
            request,
            f"{stok.urun_kodu} → {hedef_order.siparis_numarasi} siparişine başarıyla teslim edildi."
        )

        return redirect("depo_detay", depo_adi=stok.depo)

    # GET isteğinde sipariş listesi göster
    siparisler = Order.objects.all().order_by("-id")

    return render(request, "depolar/hazirdan_ver.html", {
        "stok": stok,
        "siparisler": siparisler,
    })



# AJAX ile müşteri ekleme
@login_required
def musteri_create_ajax(request):
    if request.method == "POST":
        ad = request.POST.get("ad", "").strip()
        telefon = request.POST.get("telefon", "").strip()

        if not ad:
            return JsonResponse({"success": False, "message": "Müşteri adı zorunludur."})

        m = Musteri.objects.create(ad=ad, telefon=telefon)

        return JsonResponse({
            "success": True,
            "id": m.id,
            "ad": m.ad
        })

    return JsonResponse({"success": False, "message": "Geçersiz istek"})

@login_required
def cikti_alindi(request, pk):
    """
    Siparişin 'Yazdırıldı / Çıktı Alındı' şeklinde işaretlenmesi.
    """
    order = get_object_or_404(Order, id=pk)
    order.cikti_alindi = True
    order.save(update_fields=["cikti_alindi"])

    messages.success(request, f"{order.siparis_numarasi} yazdırıldı olarak işaretlendi.")
    return redirect("order_detail", pk=pk)



@csrf_exempt
def ajax_musteri_ekle(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Geçersiz istek yöntemi."})

    ad = request.POST.get("ad", "").strip()

    if not ad:
        return JsonResponse({"success": False, "message": "Müşteri adı boş olamaz."})

    # Müşteri oluştur
    musteri = Musteri.objects.create(ad=ad)

    return JsonResponse({
        "success": True,
        "id": musteri.id,
        "ad": musteri.ad
    })

@require_POST
def musteri_pasif_yap_ajax(request):
    musteri_id = request.POST.get("id")

    if not musteri_id:
        return JsonResponse({"success": False, "message": "Müşteri ID bulunamadı."})

    try:
        musteri = Musteri.objects.get(id=musteri_id)
        musteri.aktif = False
        musteri.save()

        return JsonResponse({
            "success": True,
            "message": "Müşteri pasif yapıldı.",
            "id": musteri.id
        })

    except Musteri.DoesNotExist:
        return JsonResponse({"success": False, "message": "Müşteri bulunamadı."})


def stok_ekle(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        depo = request.POST.get("depo")
        adet = int(request.POST.get("adet", 0))

        if not depo or adet <= 0:
            messages.error(request, "Lütfen depo ve adet bilgilerini doğru girin.")
            return redirect("order_detail", pk=order.id)

        # ✔️ 1) Eski depodaki stok kaydını tamamen sil
        DepoStok.objects.filter(order=order).delete()

        # ✔️ 2) Yeni depo kaydı oluştur
        DepoStok.objects.create(
            urun_kodu=order.urun_kodu,
            renk=order.renk,
            beden=order.beden,
            adet=adet,
            depo=depo,
            aciklama=f"Stoğa Üretim: {order.siparis_numarasi}",
            order=order
        )

        # ✔️ 3) Üretim geçmişine kayıt gir
        OrderEvent.objects.create(
            order=order,
            user=request.user.username,
            gorev="hazir",
            stage="Depoya Aktarım",
            value=f"{adet} adet stoğa eklendi ({depo})",
            adet=adet,
            timestamp=timezone.now(),
        )

        messages.success(request, f"✅ {adet} adet ürün {depo} deposuna eklendi.")
        return redirect("order_detail", pk=order.id)



# 📌 Sipariş düzenleme değişikliklerini loglayan fonksiyon
def log_order_updates(request, old_obj, new_obj):
    from .models import OrderEvent

    changed = []

    # 📌 Takip edilecek alanlar
    fields = [
        "musteri", "siparis_tipi", "urun_kodu", "renk", "beden",
        "adet", "siparis_tarihi", "teslim_tarihi",
        "aciklama", "musteri_referans"
    ]

    for field in fields:
        old_val = getattr(old_obj, field, None)
        new_val = getattr(new_obj, field, None)

        # Müşteri gibi FK alanları ad ile yazalım
        if hasattr(old_val, "ad"):
            old_val = old_val.ad
        if hasattr(new_val, "ad"):
            new_val = new_val.ad

        if old_val != new_val:
            changed.append((field, old_val, new_val))

    # Her değişikliği OrderEvent olarak kaydet
    for field, old, new in changed:
        OrderEvent.objects.create(
            order=new_obj,
            user=request.user.username,
            gorev="yok",
            event_type="order_update",
            stage=field,
            value=f"{field} güncellendi",
            old_value=str(old),
            new_value=str(new)
        )


@login_required
def notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()

    # Sipariş varsa sipariş detayına yönlendir
    if notif.order:
        return redirect("order_detail", pk=notif.order.id)

    # Sipariş yoksa bildirim listesine dön
    return redirect("notification_list")

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import Notification

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, "notifications/list.html", {"notifications": notifications})


from django.shortcuts import get_object_or_404, redirect
from .models import Notification

@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()

    # Eğer bildirim siparişe bağlıysa sipariş detayına yönlendir
    if notif.order:
        return redirect("order_detail", pk=notif.order.id)

    # Değilse bildirim listesine dön
    return redirect("notification_list")


@login_required
def order_multi_create(request):

    print("📨 POST GELDİ:", request.POST)
    print("📱 USER:", request.user.username)

    if request.method == "POST":

        # ---- GENEL ALANLAR ----
        urun_kodu = request.POST.get("urun_kodu")
        urun_kodu = (urun_kodu or "").strip().upper()
        urun_tipi = request.POST.get("urun_tipi", "").strip()
        musteri_id = request.POST.get("musteri")
        print("URUN KODU:", urun_kodu)
        print("VAR MI:", ProductCost.objects.filter(urun_kodu__iexact=urun_kodu).exists())
        siparis_tipi = request.POST.get("siparis_tipi") or None
        teslim_tarihi = request.POST.get("teslim_tarihi") or None
        aciklama = request.POST.get("aciklama")

        musteri = Musteri.objects.filter(id=musteri_id).first()

        # ---- FİYAT & MALİYET (Tüm siparişler için ortak) ----
        from decimal import Decimal

        def to_decimal(value):
            if value in [None, "", "None"]:
                return None
            try:
                return Decimal(str(value))
            except:
                return None



        from decimal import Decimal

        # ---- FİYAT & MALİYET (Tüm siparişler için ortak) ----
        satis_fiyati = to_decimal(request.POST.get("satis_fiyati")) or Decimal("0")
        maliyet_uygulanan = to_decimal(request.POST.get("maliyet_uygulanan")) or Decimal("0")
        maliyet_override = to_decimal(request.POST.get("maliyet_override"))  # boşsa None kalsın
        ekstra_maliyet = to_decimal(request.POST.get("ekstra_maliyet")) or Decimal("0")

        para_birimi = request.POST.get("para_birimi") or "TRY"
        maliyet_para_birimi = request.POST.get("maliyet_para_birimi") or "TRY"

        # ✅ Eğer maliyet boşsa ProductCost tablosundan otomatik çek
        if maliyet_uygulanan == 0 and urun_kodu:
            pc = ProductCost.objects.filter(urun_kodu__iexact=urun_kodu).first()

            if pc:
                maliyet_uygulanan = pc.maliyet or Decimal("0")
                maliyet_para_birimi = pc.para_birimi or "TRY"
            else:
                maliyet_uygulanan = Decimal("0")






        created_orders = []

        # ---- ROW TESPİT ----
        row_indices = set()
        for key in request.POST.keys():
            if key.startswith("renk_row_"):
                index = key.replace("renk_row_", "")
                if index.isdigit():
                    row_indices.add(int(index))

        # ---- SATIRLARI İŞLE ----
        for i in sorted(row_indices):

            renk = request.POST.get(f"renk_row_{i}")
            bedenler = request.POST.getlist(f"beden_row_{i}[]")
            musteri_ref = request.POST.get(f"musteri_ref_row_{i}", "").strip()

            if not renk or not bedenler:
                continue

            # --- Adet güvenli ---
            adet_raw = request.POST.get(f"adet_row_{i}")
            try:
                adet_input = int(adet_raw)
                if adet_input < 1:
                    adet_input = 1
            except:
                adet_input = 1

            for beden in bedenler:

                # --- Adet güvenli ---
                adet_raw = request.POST.get(f"adet_row_{i}")
                try:
                    adet_input = int(adet_raw)
                    if adet_input < 1:
                        adet_input = 1
                except:
                    adet_input = 1

                # 🟢 Adet kadar sipariş oluştur
                for _ in range(adet_input):

                    order = Order.objects.create(
                        siparis_tipi=siparis_tipi,
                        musteri=musteri,
                        urun_kodu=urun_kodu,
                        urun_tipi=urun_tipi,
                        renk=renk,
                        beden=beden,
                        adet=1,   # Her sipariş tek adet olarak kaydedilir
                        teslim_tarihi=teslim_tarihi or None,
                        aciklama=aciklama,

                        musteri_referans=musteri_ref or None,

                        satis_fiyati=satis_fiyati,
                        para_birimi=para_birimi,
                        maliyet_uygulanan=maliyet_uygulanan,
                        maliyet_para_birimi=maliyet_para_birimi,
                        maliyet_override=maliyet_override,
                        ekstra_maliyet=ekstra_maliyet,
                    )

                    created_orders.append(order)



        messages.success(request, f"{len(created_orders)} adet sipariş başarıyla oluşturuldu!")
        return redirect("order_list")

    # --------------------------
    # GET → FORM GÖSTER
    # --------------------------

    musteriler_qs = Musteri.objects.filter(aktif=True).order_by("ad")
    renkler_qs = Renk.objects.filter(aktif=True).order_by("ad")
    bedenler_qs = Beden.objects.filter(aktif=True).order_by("ad")
    urun_kodlari_qs = UrunKod.objects.filter(aktif=True).order_by("kod")

    is_manager = request.user.groups.filter(name__in=["patron", "mudur"]).exists()

    context = {
        "musteriler": musteriler_qs,
        "renkler": renkler_qs,
        "bedenler": bedenler_qs,
        "urun_kodlari": urun_kodlari_qs,

        "aktif_musteriler": musteriler_qs,
        "aktif_renkler": renkler_qs,
        "aktif_bedenler": bedenler_qs,
        "aktif_urun_kodlari": urun_kodlari_qs,

        "is_manager": is_manager,
        "urun_tipi_secenekleri": URUN_TIPI_CHOICES,
    }

    return render(request, "multi_order/multi_order_create.html", context)

# -------------------------------------------
# 🟦 AJAX - BEDEN EKLE
# -------------------------------------------
@require_POST
@login_required
def beden_ekle_ajax(request):
    ad = request.POST.get("ad", "").strip()

    if not ad:
        return JsonResponse({"success": False, "message": "Beden adı boş olamaz."})

    beden = Beden.objects.create(ad=ad)

    return JsonResponse({
        "success": True,
        "id": beden.id,
        "ad": beden.ad
    })


# -------------------------------------------
# 🟨 AJAX - BEDEN PASİF YAP
# -------------------------------------------
@require_POST
@login_required
def beden_pasif_yap_ajax(request):
    beden_id = request.POST.get("id")

    try:
        beden = Beden.objects.get(id=beden_id)
        beden.aktif = False
        beden.save()
        return JsonResponse({"success": True})
    except Beden.DoesNotExist:
        return JsonResponse({"success": False, "message": "Beden bulunamadı."})


# -------------------------------------------
# 🟦 AJAX - ÜRÜN KODU EKLE
# -------------------------------------------
@require_POST
@login_required
def urun_kod_ekle_ajax(request):
    kod = request.POST.get("kod", "").strip()
    urun_tipi = request.POST.get("urun_tipi", "").strip()

    if not kod:
        return JsonResponse({"success": False, "message": "Ürün kodu boş olamaz."})

    valid_types = {value for value, _label in URUN_TIPI_CHOICES}
    if urun_tipi not in valid_types:
        return JsonResponse({"success": False, "message": "Geçerli bir ürün tipi seçin."})

    urun = UrunKod.objects.create(kod=kod, urun_tipi=urun_tipi)

    return JsonResponse({
        "success": True,
        "id": urun.id,
        "kod": urun.kod,
        "urun_tipi": urun.urun_tipi,
        "urun_tipi_etiketi": urun.get_urun_tipi_display(),
    })


@require_POST
@login_required
def urun_kod_tipi_guncelle_ajax(request):
    kod_id = request.POST.get("id")
    urun_tipi = request.POST.get("urun_tipi", "").strip()
    valid_types = {value for value, _label in URUN_TIPI_CHOICES}
    if urun_tipi not in valid_types:
        return JsonResponse({"success": False, "message": "Geçerli bir ürün tipi seçin."})

    try:
        urun = UrunKod.objects.get(id=kod_id)
    except UrunKod.DoesNotExist:
        return JsonResponse({"success": False, "message": "Ürün kodu bulunamadı."})

    urun.urun_tipi = urun_tipi
    urun.save(update_fields=["urun_tipi"])
    return JsonResponse({
        "success": True,
        "id": urun.id,
        "kod": urun.kod,
        "urun_tipi": urun.urun_tipi,
        "urun_tipi_etiketi": urun.get_urun_tipi_display(),
    })


# -------------------------------------------
# 🟨 AJAX - ÜRÜN KODU PASİF YAP
# -------------------------------------------
@require_POST
@login_required
def urun_kod_pasif_yap_ajax(request):
    kod_id = request.POST.get("id")

    try:
        urun = UrunKod.objects.get(id=kod_id)
        urun.aktif = False
        urun.save()
        return JsonResponse({"success": True})
    except UrunKod.DoesNotExist:
        return JsonResponse({"success": False, "message": "Ürün kodu bulunamadı."})



@require_POST
@login_required
def renk_ekle_ajax(request):
    ad = request.POST.get("ad", "").strip()
    if not ad:
        return JsonResponse({"success": False, "message": "Renk adı boş olamaz."})

    renk = Renk.objects.create(ad=ad)

    return JsonResponse({
        "success": True,
        "id": renk.id,
        "ad": renk.ad
    })

@require_POST
@login_required
def renk_pasif_yap_ajax(request):
    renk_id = request.POST.get("id")

    try:
        renk = Renk.objects.get(id=renk_id)
        renk.aktif = False
        renk.save()
        return JsonResponse({"success": True})
    except Renk.DoesNotExist:
        return JsonResponse({"success": False, "message": "Renk bulunamadı."})

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from datetime import date
from .models import MesaiKayit as Attendance  # Attendance modelini sen MesaiKayit olarak tutuyorsun

def is_manager(user):
    return user.is_staff or user.groups.filter(name__in=["patron", "mudur"]).exists()

@login_required
@user_passes_test(is_manager)
def attendance_user_month_report(request, user_id, year=None, month=None):
    target_user = get_object_or_404(User, pk=user_id)

    today = date.today()
    year = year or today.year
    month = month or today.month

    start, end = month_range(year, month)

    # ✔️ DOĞRU QUERY
    qs = Attendance.objects.filter(
        user=target_user,
        date__gte=start,
        date__lte=end
    ).order_by("date")

    att_map = {att.date: att for att in qs}

    workdays = list(iter_workdays(start, end))
    total_workdays = len(workdays)

    absent_days = [d for d in workdays if d not in att_map]

    total_late = sum(a.late_minutes for a in qs)
    total_early = sum(a.early_leave_minutes for a in qs)
    total_overtime = sum(a.overtime_minutes for a in qs)

    daily_data = []
    total_work_minutes = 0

    for d in workdays:
        att = att_map.get(d)
        if att and att.work_duration:
            dur_min = int(att.work_duration.total_seconds() // 60)
        else:
            dur_min = 0

        total_work_minutes += dur_min

        daily_data.append({
            "date": d,
            "attendance": att,
            "work_minutes": dur_min,
            "late_minutes": att.late_minutes if att else 0,
            "early_minutes": att.early_leave_minutes if att else 0,
            "overtime_minutes": att.overtime_minutes if att else 0,
        })

    return render(request, "attendance/user_month_report.html", {
        "target_user": target_user,
        "year": year,
        "month": month,
        "start": start,
        "end": end,
        "total_workdays": total_workdays,
        "absent_days": absent_days,
        "absent_count": len(absent_days),
        "total_late": total_late,
        "total_early": total_early,
        "total_overtime": total_overtime,
        "total_work_minutes": total_work_minutes,
        "daily_data": daily_data,
    })




# @login_required
# @user_passes_test(is_manager)
# def puantaj_panel(request):
#     users = User.objects.filter(is_active=True).order_by("username")
#     today = date.today()
#     return render(request, "attendance/puantaj_panel.html", {
#         "users": users,
#         "year": today.year,
#         "month": today.month,
#     })



@login_required
def order_print(request):
    ids = request.GET.get("ids")
    orders = Order.objects.filter(id__in=ids.split(",")) if ids else []
    return render(request, "core/order_print.html", {"orders": orders})

@login_required
def order_label_print(request):
    ids = request.GET.getlist("ids")
    orders = Order.objects.filter(id__in=ids)
    return render(request, "orders/order_label_print.html", {"orders": orders})


@login_required
def order_excel_export(request):
    """Seçili siparişleri veya mevcut liste filtresinin tamamını Excel'e aktarır."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    from .services.order_status import STATUS_LABELS

    financial_stages = [
        "satis_fiyati",
        "ekstra_maliyet",
        "maliyet_override",
        "maliyet_uygulanan",
    ]
    latest_event = (
        OrderEvent.objects.filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")
        .exclude(stage__in=financial_stages)
        .order_by("-timestamp", "-id")[:1]
    )
    orders = Order.objects.select_related("musteri").annotate(
        latest_stage=Subquery(latest_event.values("stage")),
        latest_value=Subquery(latest_event.values("value")),
        last_status_date=Subquery(
            latest_event.values("timestamp"), output_field=DateTimeField()
        ),
    )

    selected_ids = [value for value in request.GET.getlist("ids") if value.isdigit()]
    if selected_ids:
        orders = orders.filter(id__in=selected_ids)
    else:
        active_values = request.GET.getlist("active") or ["1"]
        if "all" not in active_values and not (
            "1" in active_values and "0" in active_values
        ):
            if "1" in active_values:
                orders = orders.filter(is_active=True)
            elif "0" in active_values:
                orders = orders.filter(is_active=False)

        list_filters = {
            "siparis_numarasi__in": request.GET.getlist("siparis_no"),
            "musteri__ad__in": request.GET.getlist("musteri"),
            "urun_kodu__in": request.GET.getlist("urun_kodu"),
            "renk__in": request.GET.getlist("renk"),
            "beden__in": request.GET.getlist("beden"),
            "siparis_tipi__in": request.GET.getlist("siparis_tipi"),
            "musteri_referans__in": request.GET.getlist("musteri_referans"),
        }
        for field, values in list_filters.items():
            if values:
                orders = orders.filter(**{field: values})

        status_values = request.GET.getlist("status")
        if status_values:
            status_query = Q()
            for (stage, value), label in STATUS_LABELS.items():
                if label in status_values:
                    status_query |= Q(latest_stage=stage, latest_value=value)
            orders = orders.filter(status_query)

        start = request.GET.get("teslim_tarihi_baslangic")
        end = request.GET.get("teslim_tarihi_bitis")
        if start:
            orders = orders.filter(teslim_tarihi__gte=start)
        if end:
            orders = orders.filter(teslim_tarihi__lte=end)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Siparişler"
    headers = [
        "Sipariş No", "Müşteri", "Ürün Kodu", "Ürün Tipi", "Müşteri Ref",
        "Adet", "Renk", "Beden", "Açıklama", "Teslim Tarihi",
        "Son Durum", "Son Durum Tarihi",
    ]
    sheet.append(headers)

    header_fill = PatternFill("solid", fgColor="4458E8")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")

    product_type_labels = dict(URUN_TIPI_CHOICES)
    for order in orders.order_by("-id"):
        status = STATUS_LABELS.get((order.latest_stage, order.latest_value))
        if not status and order.latest_stage and order.latest_value:
            status = (
                order.latest_stage.replace("_durum", "").replace("_", " ").title()
                + " → "
                + order.latest_value.replace("_", " ").title()
            )
        sheet.append([
            order.siparis_numarasi or "",
            order.musteri.ad if order.musteri else "",
            order.urun_kodu or "",
            product_type_labels.get(order.urun_tipi, order.urun_tipi or ""),
            order.musteri_referans or "",
            order.adet or 0,
            order.renk or "",
            order.beden or "",
            order.aciklama or "",
            order.teslim_tarihi,
            status or "-",
            order.last_status_date.date() if order.last_status_date else None,
        ])

    widths = [16, 24, 20, 22, 28, 10, 16, 12, 40, 16, 24, 18]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="siparisler-{timezone.localdate():%Y-%m-%d}.xlsx"'
    )
    return response

@login_required
@require_POST
def order_toggle_active(request, pk):
    order = get_object_or_404(Order, pk=pk)
    order.is_active = not order.is_active
    order.save()

    return JsonResponse({
        "success": True,
        "is_active": order.is_active
    })

from collections import Counter, defaultdict
from decimal import Decimal
import json
from datetime import timedelta, datetime
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F, Value, CharField, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.db.models import Case, When

from .models import Order, OrderEvent


@login_required
def dashboard_view(request):

    # ✅ Yetki kontrolü (patron/müdür)
    if not (request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")


    # =========================================================
    # 1) PERIOD (Bugün / Hafta / Ay)
    # =========================================================
    period = request.GET.get("period", "week")

    today = timezone.now().date()

    if period == "today":
        start_date = today
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=7)

    # =========================================================
    # 2) GENEL SAYILAR (mevcut)
    # =========================================================
    toplam_siparis = Order.objects.count()
    aktif_siparis = Order.objects.filter(is_active=True).count()
    sevk_edilen = Order.objects.filter(sevkiyat_durum="gonderildi").count()
    bekleyen = Order.objects.filter(sevkiyat_durum__in=["bekliyor", "hazirlaniyor"]).count()

    # =========================================================
    # 3) ÖZET (Seçilen period’e göre)
    # =========================================================
    son7_yeni = Order.objects.filter(siparis_tarihi__gte=start_date).count()

    son7_sevk = Order.objects.filter(
        sevkiyat_durum="gonderildi",
        siparis_tarihi__gte=start_date
    ).count()

    son7_uretim = (
        Order.objects
        .filter(is_active=True, siparis_tarihi__gte=start_date)
        .exclude(sevkiyat_durum="gonderildi")
        .count()
    )

    # =========================================================
    # 4) TOP MÜŞTERİLER / ÜRÜNLER
    # =========================================================
    top_musteriler = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)
        .exclude(musteri__isnull=True)
        .values("musteri__ad")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    top_urunler = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)
        .exclude(urun_kodu__isnull=True)
        .exclude(urun_kodu__exact="")
        .values("urun_kodu")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    last_orders = (
        Order.objects
        .select_related("musteri")
        .only("id", "siparis_numarasi", "siparis_tarihi", "urun_kodu", "renk", "beden", "musteri__ad")
        .order_by("-id")[:10]
    )

    # =========================================================
    # 5) TREND GRAFİKLERİ (SQLite-safe)
    # =========================================================

    # 5.1 Sipariş Trend (Gün Gün)  ✅ DateField ise __date KULLANMA
    siparis_dates = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)  # ✅ düzeltildi
        .values_list("siparis_tarihi", flat=True)
    )

    siparis_counts = Counter()
    for dt in siparis_dates:
        if not dt:
            continue
        # siparis_tarihi DateField ise dt zaten date'dir
        d = dt.date() if hasattr(dt, "date") else dt
        siparis_counts[d] += 1

    siparis_trend_labels = []
    siparis_trend_values = []

    d = start_date
    while d <= today:
        siparis_trend_labels.append(d.strftime("%d.%m"))
        siparis_trend_values.append(int(siparis_counts.get(d, 0)))
        d += timedelta(days=1)

    # ---------------------------------------------------------
    # 5.2 Sevkiyat Trend (Gün Gün) ✅ Python ile gruplama
    # ---------------------------------------------------------
    sevk_counts = Counter()

    # 1) Order.sevkiyat_tarihi dolu olanlar
    sevkiyat_dates = (
        Order.objects
        .filter(
            is_active=True,
            sevkiyat_durum="gonderildi",
            sevkiyat_tarihi__isnull=False,
            sevkiyat_tarihi__date__gte=start_date
        )
        .values_list("sevkiyat_tarihi", flat=True)
    )

    for dt in sevkiyat_dates:
        if not dt:
            continue
        d = dt.date() if hasattr(dt, "date") else dt
        sevk_counts[d] += 1

    # 2) sevkiyat_tarihi boş kalanlar için OrderEvent'ten türet
    sevk_event_dates = (
        OrderEvent.objects
        .filter(stage="sevkiyat_durum", value="gonderildi", timestamp__date__gte=start_date)
        .values_list("timestamp", flat=True)
    )

    for ts in sevk_event_dates:
        if not ts:
            continue
        try:
            ts_local = timezone.localtime(ts)
        except Exception:
            ts_local = ts
        d = ts_local.date()
        sevk_counts[d] += 1

    sevkiyat_trend_labels = []
    sevkiyat_trend_values = []
    d = start_date
    while d <= today:
        sevkiyat_trend_labels.append(d.strftime("%d.%m"))
        sevkiyat_trend_values.append(int(sevk_counts.get(d, 0)))
        d += timedelta(days=1)

    # 5.3 Kâr Trend ✅ DateField ise __date KULLANMA
    kar_rows = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)  # ✅ düzeltildi
        .values_list("siparis_tarihi", "satis_fiyati", "maliyet_uygulanan", "ekstra_maliyet")
    )

    kar_map = Counter()

    for dt, satis, maliyet, ekstra in kar_rows:
        if not dt:
            continue

        d = dt.date() if hasattr(dt, "date") else dt

        satis = satis or 0
        maliyet = maliyet or 0
        ekstra = ekstra or 0

        kar_map[d] += float(satis - (maliyet + ekstra))

    kar_trend_labels = []
    kar_trend_values = []

    d = start_date
    while d <= today:
        kar_trend_labels.append(d.strftime("%d.%m"))
        kar_trend_values.append(float(kar_map.get(d, 0)))
        d += timedelta(days=1)

    # =========================================================
    # 6) PERSONEL PERFORMANSI (OrderEvent)
    # =========================================================

    # 6.1 Top 10 personel
    top_personel_qs = (
        OrderEvent.objects
        .filter(timestamp__date__gte=start_date, event_type="stage")
        .values("user")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:10]
    )
    top_personel_labels = [x["user"] for x in top_personel_qs]
    top_personel_values = [x["cnt"] for x in top_personel_qs]

    # 6.2 Stacked bar (personel -> aşama)
    stage_label = Case(
        When(stage="kesim_durum", then=Value("Kesim")),
        When(stage="dikim_durum", then=Value("Dikim")),
        When(stage="susleme_durum", then=Value("Süsleme")),
        When(stage="hazir_durum", then=Value("Hazır")),
        When(stage="sevkiyat_durum", then=Value("Sevkiyat")),
        default=Value("Diğer"),
        output_field=CharField()
    )

    stack_qs = (
        OrderEvent.objects
        .filter(timestamp__date__gte=start_date, event_type="stage")
        .annotate(stage_group=stage_label)
        .values("user", "stage_group")
        .annotate(cnt=Count("id"))
    )

    stack_users = sorted(set([x["user"] for x in stack_qs]))
    stack_groups = ["Kesim", "Dikim", "Süsleme", "Hazır", "Sevkiyat", "Diğer"]

    stack_series = []
    for g in stack_groups:
        data = []
        for u in stack_users:
            val = next((x["cnt"] for x in stack_qs if x["user"] == u and x["stage_group"] == g), 0)
            data.append(val)
        stack_series.append({"name": g, "data": data})

    stack_labels = stack_users

    # ---------------------------------------------------------
    # 6.3 Heatmap (Gün / Saat) ✅ Python ile gruplama
    # ---------------------------------------------------------
    heat_events = (
        OrderEvent.objects
        .filter(timestamp__date__gte=start_date, event_type="stage")
        .values_list("timestamp", flat=True)
    )

    heat_map = defaultdict(lambda: defaultdict(int))  # day_str -> hour_str -> count
    for ts in heat_events:
        if not ts:
            continue
        try:
            ts_local = timezone.localtime(ts)
        except Exception:
            ts_local = ts

        day_str = ts_local.date().strftime("%d.%m")
        hour_str = f"{ts_local.hour:02d}:00"
        heat_map[day_str][hour_str] += 1

    heat_series = []
    # day_str sıralama: day_str formatı dd.mm olduğu için safe sıralama yapıyoruz
    def safe_sort_key(day_str):
        # yıl bilgisi yok, ama aynı period içindeyiz. Yine de bug riskini azaltmak için:
        return (int(day_str.split(".")[1]), int(day_str.split(".")[0]))

    for day_str in sorted(heat_map.keys(), key=safe_sort_key):
        data = []
        for h in range(24):
            hh = f"{h:02d}:00"
            data.append({"x": hh, "y": heat_map[day_str].get(hh, 0)})
        heat_series.append({"name": day_str, "data": data})

    # =========================================================
    # 7) MÜŞTERİ ANALİTİĞİ
    # =========================================================
    musteri_top_qs = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True, musteri__isnull=False)
        .values("musteri__ad")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:5]
    )
    musteri_top_labels = [x["musteri__ad"] for x in musteri_top_qs]
    musteri_top_values = [x["cnt"] for x in musteri_top_qs]

    musteri_ciro_qs = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True, musteri__isnull=False)
        .values("musteri__ad")
        .annotate(
            ciro=Sum(
                Coalesce(F("satis_fiyati"), ZERO, output_field=DEC),
                output_field=DEC
            )
        )
        .order_by("-ciro")[:5]
    )

    musteri_ciro_labels = [x["musteri__ad"] for x in musteri_ciro_qs]
    musteri_ciro_values = [float(x["ciro"] or 0) for x in musteri_ciro_qs]

    # =========================================================
    # 8) ÜRÜN ANALİTİĞİ
    # =========================================================
    urun_top_qs = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)
        .exclude(urun_kodu__isnull=True)
        .exclude(urun_kodu__exact="")
        .values("urun_kodu")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")[:5]
    )
    urun_top_labels = [x["urun_kodu"] or "-" for x in urun_top_qs]
    urun_top_values = [x["cnt"] for x in urun_top_qs]

    # kar_expr sadece ürün kâr analitiğinde DB üzerinden hesaplanıyor (SQLite burada problem çıkarmaz)

    kar_expr = ExpressionWrapper(
        Coalesce(F("satis_fiyati"), ZERO)
        - (Coalesce(F("maliyet_uygulanan"), ZERO) + Coalesce(F("ekstra_maliyet"), ZERO)),
        output_field=DEC
    )



    urun_kar_qs = (
        Order.objects
        .filter(siparis_tarihi__gte=start_date, is_active=True)
        .exclude(urun_kodu__isnull=True)
        .exclude(urun_kodu__exact="")
        .values("urun_kodu")
        .annotate(total_kar=Sum(kar_expr, output_field=DEC))
        .order_by("-total_kar")[:5]
    )
    urun_kar_labels = [x["urun_kodu"] or "-" for x in urun_kar_qs]
    urun_kar_values = [float(x["total_kar"] or 0) for x in urun_kar_qs]

    # =========================================================
    # 9) CONTEXT (template için tüm JSON’lar)
    # =========================================================
    context = {
        "period": period,

        "toplam_siparis": toplam_siparis,
        "aktif_siparis": aktif_siparis,
        "sevk_edilen": sevk_edilen,
        "bekleyen": bekleyen,

        "son7_yeni": son7_yeni,
        "son7_sevk": son7_sevk,
        "son7_uretim": son7_uretim,

        "top_musteriler": top_musteriler,
        "top_urunler": top_urunler,
        "last_orders": last_orders,

        "siparis_trend_labels": json.dumps(siparis_trend_labels),
        "siparis_trend_values": json.dumps(siparis_trend_values),

        "sevkiyat_trend_labels": json.dumps(sevkiyat_trend_labels),
        "sevkiyat_trend_values": json.dumps(sevkiyat_trend_values),

        "kar_trend_labels": json.dumps(kar_trend_labels),
        "kar_trend_values": json.dumps(kar_trend_values),

        "top_personel_labels": json.dumps(top_personel_labels),
        "top_personel_values": json.dumps(top_personel_values),

        "stack_labels": json.dumps(stack_labels),
        "stack_series": json.dumps(stack_series),

        "heat_series": json.dumps(heat_series),

        "musteri_top_labels": json.dumps(musteri_top_labels),
        "musteri_top_values": json.dumps(musteri_top_values),

        "musteri_ciro_labels": json.dumps(musteri_ciro_labels),
        "musteri_ciro_values": json.dumps(musteri_ciro_values),

        "urun_top_labels": json.dumps(urun_top_labels),
        "urun_top_values": json.dumps(urun_top_values),

        "urun_kar_labels": json.dumps(urun_kar_labels),
        "urun_kar_values": json.dumps(urun_kar_values),
    }

    return render(request, "reports/dashboard.html", context)






from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.db.models import OuterRef, Subquery, F, DecimalField, ExpressionWrapper, DateTimeField
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import datetime

from core.models import Order, OrderEvent


@login_required
@never_cache
def sevkiyat_finans_tablosu(request):
    # ✅ Yetki kontrolü (patron/müdür)
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    # ✅ Finans stage'leri son durum event’ini bozmasın
    finance_stages = [
        "satis_fiyati",
        "ekstra_maliyet",
        "maliyet_override",
        "maliyet_uygulanan",
    ]

    # ✅ Her sipariş için en son event’i bul (finans eventlerini hariç tutarak)
    latest_event = (
        OrderEvent.objects
        .filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")
        .exclude(stage__in=finance_stages)
        .order_by("-id")[:1]
    )

    # ✅ Order queryset
    qs = (
        Order.objects
        .select_related("musteri")
        .annotate(
            latest_stage=Subquery(latest_event.values("stage")),
            latest_value=Subquery(latest_event.values("value")),
            last_status_date=Subquery(
                latest_event.values("timestamp"),
                output_field=DateTimeField()
            ),
        )
        .filter(is_active=True)
        .filter(latest_stage="sevkiyat_durum", latest_value="gonderildi")
        .order_by("-id")
    )

    # ✅ Tarih filtresi (GET ile)
    start = request.GET.get("start")
    end = request.GET.get("end")

    if start:
        qs = qs.filter(last_status_date__date__gte=start)
    if end:
        qs = qs.filter(last_status_date__date__lte=end)

    # ✅ maliyet hesabı
    DEC = DecimalField(max_digits=12, decimal_places=2)
    ZERO = Decimal("0.00")

    toplam_maliyet_expr = ExpressionWrapper(
        Coalesce(F("maliyet_override"), ZERO, output_field=DEC)
        + Coalesce(F("maliyet_uygulanan"), ZERO, output_field=DEC)
        + Coalesce(F("ekstra_maliyet"), ZERO, output_field=DEC),
        output_field=DEC
    )

    qs = qs.annotate(
        toplam_maliyet_calc=toplam_maliyet_expr,
        kar_calc=ExpressionWrapper(
            Coalesce(F("satis_fiyati"), ZERO, output_field=DEC) - toplam_maliyet_expr,
            output_field=DEC
        )
    )

    # ✅ toplamlar
    total_ciro = sum([o.satis_fiyati or Decimal("0.00") for o in qs])
    total_maliyet = sum([o.toplam_maliyet_calc or Decimal("0.00") for o in qs])
    total_kar = total_ciro - total_maliyet

    kar_yuzde = Decimal("0.00")
    if total_ciro > 0:
        kar_yuzde = (total_kar / total_ciro) * 100

    context = {
        "orders": qs,
        "total_ciro": total_ciro,
        "total_maliyet": total_maliyet,
        "total_kar": total_kar,
        "kar_yuzde": kar_yuzde,
        "start": start,
        "end": end,
    }

    return render(request, "reports/sevkiyat_finans_tablosu.html", context)

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from core.models import OrderEvent  # senin model yolu neyse ona göre düzenle


def is_manager(user):
    return user.groups.filter(name__in=["patron", "mudur"]).exists()


@login_required
@user_passes_test(is_manager)
def personel_raporu(request):
    """
    Personel + tarih filtresiyle:
    hangi siparişte hangi üretim butonlarına basılmış raporu
    """

    # Filtreler
    selected_user = request.GET.get("user", "")
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")

    # Varsayılan tarih: son 7 gün
    today = timezone.now().date()
    default_start = today - timedelta(days=7)

    if not start_date:
        start_date = default_start.strftime("%Y-%m-%d")
    if not end_date:
        end_date = today.strftime("%Y-%m-%d")

    # Tarihleri datetime'a çevir
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    # Query
    qs = OrderEvent.objects.filter(
        event_type="stage",
        timestamp__gte=start_dt,
        timestamp__lt=end_dt,
    ).select_related("order").order_by("-timestamp")

    if selected_user:
        qs = qs.filter(user=selected_user)

    # Personel listesi (order_event.user üzerinden) ya da direkt User tablosu
    # Eğer event.user = username ise User listesini böyle çekmek daha doğru:
    users = User.objects.filter(is_active=True).order_by("username")

    # Stage/value çeviri fonksiyonu
    def format_action(e):
        stage = e.stage
        value = e.value

        ACTION_MAP = {
            "kesim_durum": {
                "basladi": "KesimBaşladı",
                "kismi_bitti": "Kısmi Keim yapıldı",
                "bitti": "Kesildi",
            },
            "dikim_durum": {
                "sıraya_alındı": "Dikim Sırasına Alındı",
                "basladi": "Dikime Başladı",
                "kismi_bitti": "Kısmi Dikim Bitti",
                "bitti": "Dikildi",
            },
            "susleme_durum": {
                "sıraya_alındı": "Süsleme Sırasına Alındı",
                "basladi": "Süslemeye Başladı",
                "kismi_bitti": "Kısmi Süslendi",
                "bitti": "Süslendi",
            },
            "dikim_fason_durumu": {
                "verildi": "Fason Dikime Verildi",
                "alindi": "Fason Dkimden Alındı",
            },
            "susleme_fason_durumu": {
                "verildi": "Fason Süslemeye Verildi",
                "alindi": "Fason Süslemeden Alındı",
            },
            "nakis_durumu": {
                "verildi": "Nakışa Verildi",
                "alindi": "Nakıştan Alındı",
            },
            "sevkiyat_durum": {
                "gonderildi": "Sevk Edildi",
            },
        }

        return ACTION_MAP.get(stage, {}).get(value, f"{stage} → {value}")


    # Listeyi template’te kolay göstermek için hazırla
    raporlar = []
    for e in qs:
        raporlar.append({
            "order_id": e.order.id,
            "siparis_no": e.order.siparis_numarasi,
            "musteri": e.order.musteri.ad if e.order.musteri else "-",
            "urun_kodu": e.order.urun_kodu or "-",
            "renk": e.order.renk or "-",
            "beden": e.order.beden or "-",
            "siparis_aciklama": e.order.aciklama or "-",
            "personel": e.user,
            "action": format_action(e),
            "islem_aciklama": e.aciklama or "-",
            "timestamp": e.timestamp,
        })

    return render(request, "reports/personel_raporu.html", {
        "users": users,
        "raporlar": raporlar,
        "selected_user": selected_user,
        "start_date": start_date,
        "end_date": end_date,
    })

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.template.loader import render_to_string
from django.db.models import OuterRef, Subquery

from .models import Order, OrderEvent

@login_required
def live_shipped_orders(request):
    # ✅ Yetki kontrolü (patron/müdür)
    if not request.user.groups.filter(name__in=["patron", "mudur"]).exists():
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    # ✅ Sevkiyat_durum eventinin en güncel kaydı
    latest_sevk_event = (
        OrderEvent.objects
        .filter(order=OuterRef("pk"), stage="sevkiyat_durum")
        .order_by("-timestamp")
    )

    # ✅ orderlara annotate
    orders = (
        Order.objects.select_related("musteri")
        .annotate(
            sevk_value=Subquery(latest_sevk_event.values("value")[:1]),
            sevk_time=Subquery(latest_sevk_event.values("timestamp")[:1]),
        )
        .filter(sevk_value="gonderildi")  # ✅ sadece sevkedildi olanlar
        .order_by("-sevk_time")
    )

    # ✅ Eğer HTMX çağırdıysa sadece tablo döndür
    if request.headers.get("HX-Request"):
        html = render_to_string("reports/_live_shipped_table.html", {"orders": orders})
        return HttpResponse(html)

    return render(request, "reports/live_shipped_orders.html", {"orders": orders})



from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok"})
