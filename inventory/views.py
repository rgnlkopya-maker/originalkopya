from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from core.models import UrunKod
from product_cards.models import Material, MaterialStockMovement, MaterialWarehouseStock, ProductCard, Warehouse
from .models import ProductStockMovement, ProductWarehouseStock


def _can_manage(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


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
    return render(request, "inventory/warehouse_detail.html", {
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
