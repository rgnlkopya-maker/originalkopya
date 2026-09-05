from decimal import Decimal, InvalidOperation
import os
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from supabase import create_client

from core.models import ProductCost, UrunKod
from .models import CURRENCY_CHOICES, ExchangeRate, Material, MaterialStockMovement, MaterialWarehouseStock, ProductCard, ProductMaterial, Warehouse


def _can_manage(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _decimal_from_post(value, default="0"):
    text = (value or default).replace(",", ".").strip()
    try:
        number = Decimal(text)
        if number < 0:
            raise InvalidOperation
        return number
    except (InvalidOperation, ValueError):
        raise ValueError("Geçerli bir tutar girin.")


def _date_from_post(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Geçerli bir tarih girin.")


def _warehouse_from_post(request, key="warehouse"):
    warehouse_id=(request.POST.get(key) or "").strip()
    if warehouse_id:
        return get_object_or_404(Warehouse, pk=warehouse_id, aktif=True)
    return Warehouse.objects.filter(kod="MERKEZ", aktif=True).first() or Warehouse.objects.filter(aktif=True).first()


def _upload_image(uploaded_file, folder, code):
    if not uploaded_file:
        return ""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase ayarları eksik.")
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
    safe_code = "".join(ch for ch in code if ch.isalnum() or ch in ("-", "_")) or "kart"
    path = f"{folder}/{safe_code}/{uuid.uuid4().hex}{ext}"
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    bucket = client.storage.from_(settings.SUPABASE_BUCKET_NAME)
    bucket.upload(path, uploaded_file.read(), file_options={"content-type": uploaded_file.content_type or "application/octet-stream", "upsert": "false"})
    return bucket.get_public_url(path)


def recalculate_approved_product_costs():
    approved_codes = set(ProductCost.objects.filter(is_active=True).values_list("urun_kodu", flat=True))
    if not approved_codes:
        return 0
    cards = ProductCard.objects.select_related("urun").prefetch_related("materials__material").filter(urun__kod__in=approved_codes)
    updated = 0
    for card in cards:
        total = card.toplam_maliyet.quantize(Decimal("0.01"))
        ProductCost.objects.filter(urun_kodu=card.urun.kod, is_active=True).update(maliyet=total, para_birimi="TRY")
        updated += 1
    return updated


def fetch_tcmb_usd_rate():
    request = urllib.request.Request("https://www.tcmb.gov.tr/kurlar/today.xml", headers={"User-Agent": "MoliApp/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        xml_data = response.read()
    root = ET.fromstring(xml_data)
    usd_node = root.find(".//Currency[@CurrencyCode='USD']")
    if usd_node is None:
        raise RuntimeError("TCMB verisinde USD bulunamadı.")
    selling_text = usd_node.findtext("ForexSelling") or usd_node.findtext("BanknoteSelling")
    if not selling_text:
        raise RuntimeError("TCMB USD satış kuru alınamadı.")
    usd_try = Decimal(selling_text.strip().replace(",", "."))
    source_date = root.attrib.get("Date", "")
    today = timezone.localdate()
    rate, _ = ExchangeRate.objects.update_or_create(rate_date=today, defaults={"usd_try": usd_try, "source_date": source_date})
    recalculate_approved_product_costs()
    return rate


def ensure_daily_rate():
    today = timezone.localdate()
    rate = ExchangeRate.objects.filter(rate_date=today).first()
    if rate:
        return rate, None
    try:
        return fetch_tcmb_usd_rate(), None
    except Exception as exc:
        return ExchangeRate.objects.order_by("-rate_date").first(), str(exc)


@login_required
@require_POST
def refresh_exchange_rate(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    try:
        rate = fetch_tcmb_usd_rate()
        messages.success(request, f"TCMB USD satış kuru güncellendi: 1 USD = {rate.usd_try} TL. Onaylı ürün maliyetleri de yenilendi.")
    except Exception as exc:
        messages.error(request, f"Kur güncellenemedi: {exc}")
    return redirect(request.POST.get("next") or "product_card_list")


@login_required
def product_card_list(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    current_rate, rate_error = ensure_daily_rate()
    cards = ProductCard.objects.select_related("urun").prefetch_related("materials").order_by("urun__kod")
    q = (request.GET.get("q") or "").strip()
    if q:
        cards = cards.filter(urun__kod__icontains=q)
    return render(request, "product_cards/list.html", {"cards": cards, "q": q, "current_rate": current_rate, "rate_error": rate_error})


@login_required
def product_card_detail(request, card_id):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    current_rate, rate_error = ensure_daily_rate()
    card = get_object_or_404(ProductCard.objects.select_related("urun"), pk=card_id)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_card":
            card.aciklama = (request.POST.get("aciklama") or "").strip(); urun_tipi = (request.POST.get("urun_tipi") or "").strip()
            if urun_tipi: card.urun.urun_tipi = urun_tipi; card.urun.save(update_fields=["urun_tipi"])
            uploaded_image = request.FILES.get("product_image")
            if uploaded_image:
                try: card.image_url = _upload_image(uploaded_image, "product-cards", card.urun.kod)
                except Exception as exc: messages.error(request, f"Ürün resmi yüklenemedi: {exc}"); return redirect("product_card_detail", card_id=card.id)
            if request.POST.get("remove_image") == "1": card.image_url = ""
            card.save(); messages.success(request, "Ürün kartı güncellendi.")
        elif action == "add_material":
            material_id = request.POST.get("material_id"); miktar_text = (request.POST.get("miktar") or "").replace(",", ".")
            try:
                miktar = Decimal(miktar_text)
                if miktar <= 0: raise InvalidOperation
            except (InvalidOperation, ValueError): messages.error(request, "Geçerli bir sarfiyat miktarı girin."); return redirect("product_card_detail", card_id=card.id)
            material = get_object_or_404(Material, pk=material_id, aktif=True)
            ProductMaterial.objects.update_or_create(product_card=card, material=material, defaults={"miktar": miktar, "kullanim_asamasi": material.kullanim_asamasi, "notlar": (request.POST.get("notlar") or "").strip()})
            if ProductCost.objects.filter(urun_kodu=card.urun.kod, is_active=True).exists(): recalculate_approved_product_costs()
            messages.success(request, f"Malzeme reçeteye {material.get_kullanim_asamasi_display()} olarak eklendi/güncellendi.")
        elif action == "remove_material":
            usage = get_object_or_404(ProductMaterial, pk=request.POST.get("usage_id"), product_card=card); usage.delete()
            if ProductCost.objects.filter(urun_kodu=card.urun.kod, is_active=True).exists(): recalculate_approved_product_costs()
            messages.success(request, "Malzeme reçeteden kaldırıldı.")
        elif action in {"save_costs", "approve_cost"}:
            try:
                card.finansman_maliyeti = _decimal_from_post(request.POST.get("finansman_maliyeti")); card.nakis_maliyeti = _decimal_from_post(request.POST.get("nakis_maliyeti")); card.genel_gider = _decimal_from_post(request.POST.get("genel_gider")); card.iscilik_maliyeti = _decimal_from_post(request.POST.get("iscilik_maliyeti")); card.paketleme_maliyeti = _decimal_from_post(request.POST.get("paketleme_maliyeti"))
            except ValueError as exc: messages.error(request, str(exc)); return redirect("product_card_detail", card_id=card.id)
            valid_currencies = {choice[0] for choice in CURRENCY_CHOICES}
            card.finansman_para_birimi = request.POST.get("finansman_para_birimi") if request.POST.get("finansman_para_birimi") in valid_currencies else "TRY"; card.nakis_para_birimi = request.POST.get("nakis_para_birimi") if request.POST.get("nakis_para_birimi") in valid_currencies else "TRY"; card.genel_gider_para_birimi = request.POST.get("genel_gider_para_birimi") if request.POST.get("genel_gider_para_birimi") in valid_currencies else "TRY"; card.iscilik_para_birimi = request.POST.get("iscilik_para_birimi") if request.POST.get("iscilik_para_birimi") in valid_currencies else "TRY"; card.paketleme_para_birimi = request.POST.get("paketleme_para_birimi") if request.POST.get("paketleme_para_birimi") in valid_currencies else "TRY"
            card.save(update_fields=["finansman_maliyeti", "finansman_para_birimi", "nakis_maliyeti", "nakis_para_birimi", "genel_gider", "genel_gider_para_birimi", "iscilik_maliyeti", "iscilik_para_birimi", "paketleme_maliyeti", "paketleme_para_birimi", "updated_at"])
            if action == "save_costs":
                if ProductCost.objects.filter(urun_kodu=card.urun.kod, is_active=True).exists(): recalculate_approved_product_costs()
                messages.success(request, "Maliyet kalemleri kaydedildi. Güncel kurla toplam yeniden hesaplandı.")
            else:
                total = card.toplam_maliyet.quantize(Decimal("0.01")); ProductCost.objects.update_or_create(urun_kodu=card.urun.kod, defaults={"maliyet": total, "para_birimi": "TRY", "is_active": True}); messages.success(request, f"{card.urun.kod} maliyeti güncel kurla {total} TL olarak Ürün Maliyetleri listesine kaydedildi.")
        return redirect("product_card_detail", card_id=card.id)
    materials = Material.objects.filter(aktif=True).order_by("ad"); usages = list(card.materials.select_related("material").all()); material_total = sum((usage.satir_maliyeti for usage in usages), Decimal("0")); current_product_cost = ProductCost.objects.filter(urun_kodu=card.urun.kod, is_active=True).first()
    return render(request, "product_cards/detail.html", {"card": card, "materials": materials, "usages": usages, "material_total": material_total, "calculated_total": card.toplam_maliyet, "current_product_cost": current_product_cost, "current_rate": current_rate, "rate_error": rate_error, "currency_choices": CURRENCY_CHOICES, "urun_tipi_choices": UrunKod._meta.get_field("urun_tipi").choices, "material_stage_choices": ProductMaterial.STAGE_CHOICES})


@login_required
def material_list(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    current_rate, rate_error = ensure_daily_rate(); warehouses=Warehouse.objects.filter(aktif=True).order_by("ad")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            kod=(request.POST.get("kod") or "").strip().upper(); ad=(request.POST.get("ad") or "").strip(); birim=(request.POST.get("birim") or "M").strip(); kategori=(request.POST.get("kategori") or "DIGER").strip(); kullanim_asamasi=(request.POST.get("kullanim_asamasi") or "KESIM").strip(); para_birimi=(request.POST.get("birim_maliyet_para_birimi") or "TRY").strip(); warehouse=_warehouse_from_post(request)
            if para_birimi not in {"TRY","USD"}: para_birimi="TRY"
            if kategori not in {c[0] for c in Material.CATEGORY_CHOICES}: kategori="DIGER"
            if kullanim_asamasi not in {c[0] for c in Material.USAGE_STAGE_CHOICES}: kullanim_asamasi="KESIM"
            try: stok=_decimal_from_post(request.POST.get("stok_miktari")); kritik_stok=_decimal_from_post(request.POST.get("kritik_stok")); birim_maliyet=_decimal_from_post(request.POST.get("birim_maliyet")); son_alis_tarihi=_date_from_post(request.POST.get("son_alis_tarihi"))
            except ValueError as exc: messages.error(request,str(exc)); return redirect("material_list")
            if kod and ad:
                with transaction.atomic():
                    material,created=Material.objects.update_or_create(kod=kod,defaults={"ad":ad,"kategori":kategori,"kullanim_asamasi":kullanim_asamasi,"birim":birim,"kritik_stok":kritik_stok,"tedarikci":(request.POST.get("tedarikci") or "").strip(),"aciklama":(request.POST.get("aciklama") or "").strip(),"birim_maliyet":birim_maliyet,"birim_maliyet_para_birimi":para_birimi,"son_alis_tarihi":son_alis_tarihi,"aktif":True})
                    if created and stok>0 and warehouse:
                        ws,_=MaterialWarehouseStock.objects.get_or_create(material=material,warehouse=warehouse,defaults={"miktar":0}); before=ws.miktar; ws.miktar+=stok; ws.save(); material.sync_total_stock(); MaterialStockMovement.objects.create(material=material,warehouse=warehouse,movement_type="BASLANGIC",miktar=stok,onceki_stok=before,sonraki_stok=ws.miktar,aciklama="Malzeme kartı açılış stoğu",islem_yapan=request.user)
                    elif not created and stok!=material.stok_miktari: messages.warning(request,"Mevcut kartın stoğu kart kaydından değiştirilmedi. Stok için hareket ekleyin.")
                uploaded_image=request.FILES.get("material_image")
                if uploaded_image:
                    try: material.image_url=_upload_image(uploaded_image,"material-cards",material.kod); material.save(update_fields=["image_url"])
                    except Exception as exc: messages.error(request,f"Malzeme resmi yüklenemedi: {exc}"); return redirect("material_list")
                recalculate_approved_product_costs(); messages.success(request,"Malzeme kartı kaydedildi.")
        elif action == "update_info":
            material=get_object_or_404(Material,pk=request.POST.get("id"),aktif=True)
            try: material.kritik_stok=_decimal_from_post(request.POST.get("kritik_stok")); material.son_alis_tarihi=_date_from_post(request.POST.get("son_alis_tarihi"))
            except ValueError as exc: messages.error(request,str(exc)); return redirect("material_list")
            kategori=request.POST.get("kategori") or "DIGER"; kullanim_asamasi=request.POST.get("kullanim_asamasi") or "KESIM"; material.kategori=kategori if kategori in {c[0] for c in Material.CATEGORY_CHOICES} else "DIGER"; material.kullanim_asamasi=kullanim_asamasi if kullanim_asamasi in {c[0] for c in Material.USAGE_STAGE_CHOICES} else "KESIM"; material.tedarikci=(request.POST.get("tedarikci") or "").strip(); material.aciklama=(request.POST.get("aciklama") or "").strip(); material.save(update_fields=["kategori","kullanim_asamasi","kritik_stok","tedarikci","aciklama","son_alis_tarihi","updated_at"]); ProductMaterial.objects.filter(material=material).update(kullanim_asamasi=material.kullanim_asamasi); messages.success(request,"Malzeme bilgileri ve kullanım aşaması güncellendi.")
        elif action == "stock_movement":
            material_id=request.POST.get("id"); movement_type=(request.POST.get("movement_type") or "").strip(); warehouse=_warehouse_from_post(request); allowed_types={"GIRIS","CIKIS","IADE","FIRE","DUZELTME_ARTI","DUZELTME_EKSI"}
            if movement_type not in allowed_types or not warehouse: messages.error(request,"Geçerli depo ve stok hareketi seçin."); return redirect("material_list")
            try:
                miktar=_decimal_from_post(request.POST.get("miktar"))
                if miktar<=0: raise ValueError("Stok hareket miktarı sıfırdan büyük olmalıdır.")
            except ValueError as exc: messages.error(request,str(exc)); return redirect("material_list")
            with transaction.atomic():
                material=Material.objects.select_for_update().get(pk=material_id,aktif=True); ws,_=MaterialWarehouseStock.objects.select_for_update().get_or_create(material=material,warehouse=warehouse,defaults={"miktar":0}); onceki=ws.miktar
                if movement_type in {"CIKIS","FIRE","DUZELTME_EKSI"}:
                    sonraki=onceki-miktar
                    if sonraki<0: messages.error(request,f"{warehouse.ad} deposunda yetersiz stok. Mevcut: {onceki} {material.get_birim_display()}."); return redirect("material_list")
                else: sonraki=onceki+miktar
                ws.miktar=sonraki; ws.save(update_fields=["miktar","updated_at"]); material.sync_total_stock()
                if movement_type=="GIRIS":
                    try: movement_cost=_decimal_from_post(request.POST.get("hareket_birim_maliyet"),default="0")
                    except ValueError: movement_cost=Decimal("0")
                    movement_currency=request.POST.get("hareket_para_birimi") or material.birim_maliyet_para_birimi
                    if movement_cost>0: material.birim_maliyet=movement_cost; material.birim_maliyet_para_birimi=movement_currency if movement_currency in {"TRY","USD"} else "TRY"
                    material.son_alis_tarihi=timezone.localdate(); material.save(update_fields=["birim_maliyet","birim_maliyet_para_birimi","son_alis_tarihi","updated_at"])
                MaterialStockMovement.objects.create(material=material,warehouse=warehouse,movement_type=movement_type,miktar=miktar,onceki_stok=onceki,sonraki_stok=sonraki,aciklama=(request.POST.get("hareket_aciklama") or "").strip(),islem_yapan=request.user)
            if movement_type=="GIRIS": recalculate_approved_product_costs()
            messages.success(request,f"{warehouse.ad} stok hareketi kaydedildi. Yeni depo stoğu: {sonraki} {material.get_birim_display()}.")
        elif action == "transfer":
            material=get_object_or_404(Material,pk=request.POST.get("id"),aktif=True); source=_warehouse_from_post(request,"source_warehouse"); target=_warehouse_from_post(request,"target_warehouse")
            try:
                miktar=_decimal_from_post(request.POST.get("miktar"))
                if miktar<=0: raise ValueError("Transfer miktarı sıfırdan büyük olmalıdır.")
            except ValueError as exc: messages.error(request,str(exc)); return redirect("material_list")
            if not source or not target or source.id==target.id: messages.error(request,"Kaynak ve hedef depolar farklı olmalıdır."); return redirect("material_list")
            with transaction.atomic():
                source_stock,_=MaterialWarehouseStock.objects.select_for_update().get_or_create(material=material,warehouse=source,defaults={"miktar":0}); target_stock,_=MaterialWarehouseStock.objects.select_for_update().get_or_create(material=material,warehouse=target,defaults={"miktar":0})
                if source_stock.miktar<miktar: messages.error(request,f"{source.ad} deposunda yeterli stok yok."); return redirect("material_list")
                sb=source_stock.miktar; tb=target_stock.miktar; source_stock.miktar-=miktar; target_stock.miktar+=miktar; source_stock.save(); target_stock.save(); aciklama=f"{source.ad} → {target.ad}"; MaterialStockMovement.objects.create(material=material,warehouse=source,movement_type="TRANSFER_CIKIS",miktar=miktar,onceki_stok=sb,sonraki_stok=source_stock.miktar,aciklama=aciklama,islem_yapan=request.user); MaterialStockMovement.objects.create(material=material,warehouse=target,movement_type="TRANSFER_GIRIS",miktar=miktar,onceki_stok=tb,sonraki_stok=target_stock.miktar,aciklama=aciklama,islem_yapan=request.user); material.sync_total_stock()
            messages.success(request,f"{miktar} {material.get_birim_display()} {source.ad} → {target.ad} transfer edildi.")
        elif action == "update_cost":
            material=get_object_or_404(Material,pk=request.POST.get("id"),aktif=True)
            try: material.birim_maliyet=_decimal_from_post(request.POST.get("birim_maliyet"))
            except ValueError as exc: messages.error(request,str(exc)); return redirect("material_list")
            para_birimi=request.POST.get("birim_maliyet_para_birimi") or "TRY"; material.birim_maliyet_para_birimi=para_birimi if para_birimi in {"TRY","USD"} else "TRY"; material.save(update_fields=["birim_maliyet","birim_maliyet_para_birimi","updated_at"]); recalculate_approved_product_costs(); messages.success(request,"Malzeme birim maliyeti güncellendi; bağlı onaylı ürün maliyetleri de yenilendi.")
        elif action == "update_image":
            material=get_object_or_404(Material,pk=request.POST.get("id"),aktif=True); uploaded_image=request.FILES.get("material_image")
            if uploaded_image:
                try: material.image_url=_upload_image(uploaded_image,"material-cards",material.kod); material.save(update_fields=["image_url"]); messages.success(request,"Malzeme görseli güncellendi.")
                except Exception as exc: messages.error(request,f"Malzeme resmi yüklenemedi: {exc}")
            elif request.POST.get("remove_image")=="1": material.image_url=""; material.save(update_fields=["image_url"]); messages.success(request,"Malzeme görseli kaldırıldı.")
        elif action == "deactivate":
            material=get_object_or_404(Material,pk=request.POST.get("id")); material.aktif=False; material.save(update_fields=["aktif"]); messages.success(request,"Malzeme pasife alındı.")
        return redirect("material_list")
    materials=Material.objects.filter(aktif=True).prefetch_related("stock_movements__warehouse","warehouse_stocks__warehouse").order_by("ad"); recent_movements=MaterialStockMovement.objects.select_related("material","warehouse","islem_yapan").filter(material__aktif=True)[:40]; critical_count=sum(1 for material in materials if material.kritik_mi)
    return render(request,"product_cards/material_list.html",{"materials":materials,"recent_movements":recent_movements,"critical_count":critical_count,"current_rate":current_rate,"rate_error":rate_error,"category_choices":Material.CATEGORY_CHOICES,"usage_stage_choices":Material.USAGE_STAGE_CHOICES,"movement_choices":[c for c in MaterialStockMovement.MOVEMENT_CHOICES if c[0] in {"GIRIS","CIKIS","IADE","FIRE","DUZELTME_ARTI","DUZELTME_EKSI"}],"warehouses":warehouses})


@login_required
def warehouse_inventory(request):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    selected=(request.GET.get("depo") or "").strip(); q=(request.GET.get("q") or "").strip(); warehouses=Warehouse.objects.filter(aktif=True).order_by("ad"); stocks=MaterialWarehouseStock.objects.select_related("material","warehouse").filter(material__aktif=True,warehouse__aktif=True)
    if selected: stocks=stocks.filter(warehouse__kod=selected)
    if q: stocks=stocks.filter(models.Q(material__kod__icontains=q)|models.Q(material__ad__icontains=q)|models.Q(material__tedarikci__icontains=q))
    rows=list(stocks.order_by("warehouse__ad","material__ad")); summary=[]
    for warehouse in warehouses:
        wstocks=MaterialWarehouseStock.objects.filter(warehouse=warehouse,material__aktif=True); summary.append({"warehouse":warehouse,"kalem":wstocks.filter(miktar__gt=0).count(),"toplam_hareket":MaterialStockMovement.objects.filter(warehouse=warehouse).count()})
    return render(request,"product_cards/warehouse_inventory.html",{"warehouses":warehouses,"rows":rows,"summary":summary,"selected":selected,"q":q})
