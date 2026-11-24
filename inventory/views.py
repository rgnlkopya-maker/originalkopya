from app_settings.access import has_access, order_scope_allows
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from core.models import UrunKod, Renk, Beden, Order, OrderEvent
from product_cards.models import Material, MaterialStockMovement, MaterialWarehouseStock, ProductCard, Warehouse
from .models import ProductStockMovement, ProductWarehouseStock, PreparationStock, PreparationUse, LACE_STAGES
from django.views.decorators.http import require_http_methods, require_POST
from core.services.order_status import sync_order_stage_from_events


def _can_manage(user):
    return has_access(user, "can_view_depots")


@login_required
def warehouse_detail(request, code):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    q = (request.GET.get("q") or "").strip()
    material_stocks = MaterialWarehouseStock.objects.select_related("material").filter(warehouse=warehouse, material__aktif=True, miktar__gt=0)
    product_stocks = ProductWarehouseStock.objects.select_related("product").filter(warehouse=warehouse, quantity__gt=0)
    if q:
        material_stocks = material_stocks.filter(Q(material__kod__icontains=q) | Q(material__ad__icontains=q))
        product_stocks = product_stocks.filter(product__kod__icontains=q)
    material_stocks = material_stocks.order_by("material__ad")
    product_stocks = product_stocks.order_by("product__kod")
    preparations = PreparationStock.objects.select_related("product").filter(warehouse=warehouse, remaining__gt=0)
    if q:
        preparations = preparations.filter(Q(product__kod__icontains=q) | Q(color__icontains=q) | Q(size__icontains=q))
    return render(request, "inventory/warehouse_detail.html", {
        "preparations": preparations, "lace_stages": LACE_STAGES, "colors": Renk.objects.filter(aktif=True).order_by("ad"), "sizes": Beden.objects.filter(aktif=True).order_by("ad"),
        "warehouse": warehouse, "q": q, "material_stocks": material_stocks, "product_stocks": product_stocks,
        "material_count": material_stocks.count(), "product_count": product_stocks.count(),
        "materials": Material.objects.filter(aktif=True).order_by("ad"), "products": UrunKod.objects.filter(aktif=True).order_by("kod"),
    })


@login_required
def material_card(request, code, material_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    material = get_object_or_404(Material, pk=material_id, aktif=True)
    stock, _ = MaterialWarehouseStock.objects.get_or_create(material=material, warehouse=warehouse, defaults={"miktar": 0})
    movements = MaterialStockMovement.objects.select_related("islem_yapan", "order").filter(material=material, warehouse=warehouse)[:100]
    return render(request, "inventory/material_card.html", {"warehouse": warehouse, "material": material, "stock": stock, "movements": movements})


@login_required
def product_card(request, code, product_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    product = get_object_or_404(UrunKod, pk=product_id, aktif=True)
    stock, _ = ProductWarehouseStock.objects.get_or_create(product=product, warehouse=warehouse, defaults={"quantity": 0})
    movements = ProductStockMovement.objects.select_related("user").filter(product=product, warehouse=warehouse)[:100]
    product_info = ProductCard.objects.filter(urun=product).first()
    return render(request, "inventory/product_card.html", {"warehouse": warehouse, "product": product, "product_info": product_info, "stock": stock, "movements": movements})


@login_required
def add_material_movement(request, code):
    if request.method != "POST" or not _can_manage(request.user): return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    material = get_object_or_404(Material, pk=request.POST.get("material_id"), aktif=True)
    movement_type = request.POST.get("movement_type") or "GIRIS"
    try:
        amount = Decimal((request.POST.get("quantity") or "0").replace(",", "."))
        if amount <= 0: raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, "Geçerli bir miktar girin."); return redirect("inventory_warehouse_detail", code=code)
    negative = movement_type in {"CIKIS", "FIRE", "DUZELTME_EKSI"}
    with transaction.atomic():
        stock, _ = MaterialWarehouseStock.objects.select_for_update().get_or_create(material=material, warehouse=warehouse, defaults={"miktar": 0})
        before = stock.miktar
        after = before - amount if negative else before + amount
        if after < 0:
            messages.error(request, "Stok miktarı eksiye düşemez."); return redirect("inventory_warehouse_detail", code=code)
        stock.miktar = after; stock.save(update_fields=["miktar", "updated_at"]); material.sync_total_stock()
        MaterialStockMovement.objects.create(material=material, warehouse=warehouse, movement_type=movement_type, miktar=amount, onceki_stok=before, sonraki_stok=after, aciklama=(request.POST.get("note") or "").strip(), islem_yapan=request.user)
    messages.success(request, f"{material.ad} stok hareketi kaydedildi.")
    return redirect("inventory_material_card", code=code, material_id=material.id)


@login_required
def add_product_movement(request, code):
    if request.method != "POST" or not _can_manage(request.user): return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    product = get_object_or_404(UrunKod, pk=request.POST.get("product_id"), aktif=True)
    movement_type = request.POST.get("movement_type") or "GIRIS"
    try:
        amount = int(request.POST.get("quantity") or 0)
        if amount <= 0: raise ValueError
    except ValueError:
        messages.error(request, "Geçerli bir adet girin."); return redirect("inventory_warehouse_detail", code=code)
    negative = movement_type in {"CIKIS", "DUZELTME_EKSI"}
    with transaction.atomic():
        stock, _ = ProductWarehouseStock.objects.select_for_update().get_or_create(product=product, warehouse=warehouse, defaults={"quantity": 0})
        before = stock.quantity; after = before - amount if negative else before + amount
        if after < 0:
            messages.error(request, "Stok adedi eksiye düşemez."); return redirect("inventory_warehouse_detail", code=code)
        stock.quantity = after; stock.save(update_fields=["quantity", "updated_at"])
        ProductStockMovement.objects.create(product=product, warehouse=warehouse, movement_type=movement_type, quantity=amount, previous_stock=before, resulting_stock=after, note=(request.POST.get("note") or "").strip(), user=request.user)
    messages.success(request, f"{product.kod} stok hareketi kaydedildi.")
    return redirect("inventory_product_card", code=code, product_id=product.id)


@login_required
@require_POST
def add_preparation(request, code):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    product = get_object_or_404(UrunKod, pk=request.POST.get("product_id"), aktif=True)
    color = (request.POST.get("color") or "").strip()
    size = (request.POST.get("size") or "").strip()
    stage = request.POST.get("stage")
    try:
        quantity = int(request.POST.get("quantity", "0"))
        if not 0 < quantity <= 100000:
            raise ValueError
        if not Renk.objects.filter(ad=color, aktif=True).exists() or (size and not Beden.objects.filter(ad=size, aktif=True).exists()) or stage not in dict(LACE_STAGES):
            raise ValueError
    except ValueError:
        messages.error(request, "Geçerli renk, beden, hazırlık durumu ve adet girin.")
        return redirect("inventory_warehouse_detail", code=code)
    PreparationStock.objects.create(
        warehouse=warehouse, product=product, color=color, size=size, stage=stage,
        initial_quantity=quantity, remaining=quantity, prepared_by=request.user.username[:100],
        note=(request.POST.get("note") or "").strip()[:255],
    )
    messages.success(request, "Üretim hazırlığı stoğa eklendi.")
    return redirect("inventory_warehouse_detail", code=code)


def _can_use_preparation(user, order):
    return (_can_manage(user) and has_access(user, "can_edit_orders") and
            order_scope_allows(user, order) and order.is_active and
            order.musteri_id is not None and order.siparis_tipi not in ("STOK", "MALZEME", "KONSINYE") and
            order.sevkiyat_durum != "gonderildi")


def _matching_preparations(order):
    return PreparationStock.objects.filter(
        product__kod__iexact=order.urun_kodu or "", warehouse__aktif=True,
        color__iexact=order.renk or "", remaining__gt=0,
    ).filter(Q(size="") | Q(size__iexact=order.beden or ""))


@login_required
@require_http_methods(["GET", "POST"])
def use_preparation(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _can_use_preparation(request.user, order):
        return HttpResponseForbidden("Bu sipariş için hazırlık stoğu kullanılamaz.")
    if request.method == "POST":
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
            if not _can_use_preparation(request.user, order):
                return HttpResponseForbidden("Bu sipariş için hazırlık stoğu kullanılamaz.")
            stock = _matching_preparations(order).select_for_update().filter(pk=request.POST.get("stock_id")).first()
            if not stock:
                messages.error(request, "Uygun hazırlık stoğu bulunamadı.")
                return redirect("inventory_use_preparation", order_id=order_id)
            # Bir sipariş kaydı için bir adet. Etek ve beden ayrı karşılanabilir;
            # tam takım ile kısmi hazırlıkların üst üste düşülmesi engellenir.
            full = {"danteli_ayarlandi", "takim_olarak_danteli_ayarlandi"}
            conflicts = set(dict(LACE_STAGES)) if stock.stage in full else full | {stock.stage}
            if PreparationUse.objects.filter(order=order, stock__stage__in=conflicts).exists() or OrderEvent.objects.filter(order=order, stage="malzeme_durum", value__in=conflicts).exists():
                messages.error(request, "Bu hazırlık siparişte zaten kayıtlı veya karşılanmış.")
                return redirect("inventory_use_preparation", order_id=order_id)
            stock.remaining -= 1
            stock.save(update_fields=["remaining"])
            event = OrderEvent.objects.create(order=order, user=stock.prepared_by, gorev="yok",
                stage="malzeme_durum", value=stock.stage, adet=1, event_type="stage",
                timestamp=stock.created_at, aciklama=f"Hazırlık stoğundan karşılandı: {stock.warehouse.ad} / #{stock.pk}")
            PreparationUse.objects.create(stock=stock, order=order, event=event, user=request.user)
            sync_order_stage_from_events(order, "malzeme_durum")
        messages.success(request, "Bir adet hazırlık stoğundan düşüldü ve üretim geçmişi aktarıldı.")
        return redirect("order_detail", pk=order_id)
    return render(request, "inventory/use_preparation.html", {
        "order": order, "stocks": _matching_preparations(order).select_related("warehouse", "product"),
        "uses": PreparationUse.objects.filter(order=order).select_related("stock", "user"),
    })
