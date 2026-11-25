from app_settings.access import has_access
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from core.models import UrunKod, Renk
from product_cards.models import Material, MaterialStockMovement, MaterialWarehouseStock, ProductCard, Warehouse
from .models import ProductStockMovement, ProductWarehouseStock


def _can_cancel_movement(user):
    return _can_manage(user) and (user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists())


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
        matching_materials = material_stocks.filter(Q(material__kod__icontains=q) | Q(material__ad__icontains=q) | Q(renk__icontains=q)).order_by().values("material_id")
        material_stocks = material_stocks.filter(material_id__in=matching_materials)
        product_stocks = product_stocks.filter(product__kod__icontains=q)
    grouped_materials = {}
    for stock_row in material_stocks.order_by("material__ad", "material_id", "renk"):
        card = grouped_materials.setdefault(stock_row.material_id, {"material": stock_row.material, "miktar": Decimal("0")})
        card["miktar"] += stock_row.miktar
    material_stocks = list(grouped_materials.values())
    product_stocks = product_stocks.order_by("product__kod")
    return render(request, "inventory/warehouse_detail.html", {
        "warehouse": warehouse, "q": q, "material_stocks": material_stocks, "product_stocks": product_stocks,
        "material_count": len(material_stocks), "product_count": product_stocks.count(),
        "colors": Renk.objects.filter(aktif=True).order_by("ad"), "materials": Material.objects.filter(aktif=True).order_by("ad"), "products": UrunKod.objects.filter(aktif=True).order_by("kod"),
    })


@login_required
def material_card(request, code, material_id):
    if not _can_manage(request.user): return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    material = get_object_or_404(Material, pk=material_id, aktif=True)
    stocks = MaterialWarehouseStock.objects.filter(material=material, warehouse=warehouse).order_by("renk")
    stock = {"miktar": stocks.aggregate(total=Sum("miktar"))["total"] or Decimal("0")}
    colors = Renk.objects.filter(aktif=True).order_by("ad")
    movements = MaterialStockMovement.objects.select_related("islem_yapan", "order").filter(material=material, warehouse=warehouse)[:100]
    cancelable = _can_cancel_movement(request.user)
    for movement in movements:
        movement.can_cancel = cancelable and _is_manual_cancelable(movement)
    return render(request, "inventory/material_card.html", {"warehouse": warehouse, "material": material, "stock": stock, "movements": movements, "stocks": stocks, "colors": colors})


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
    if movement_type not in {"GIRIS", "CIKIS", "IADE", "FIRE", "DUZELTME_ARTI", "DUZELTME_EKSI"}:
        return HttpResponseForbidden("Geçersiz stok hareketi.")
    try:
        amount = Decimal((request.POST.get("quantity") or "0").replace(",", "."))
        if amount <= 0: raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, "Geçerli bir miktar girin."); return redirect("inventory_warehouse_detail", code=code)
    renk = (request.POST.get("renk") or "").strip()
    if renk and not Renk.objects.filter(ad=renk, aktif=True).exists():
        messages.error(request, "Aktif bir renk seçin."); return redirect("inventory_warehouse_detail", code=code)
    negative = movement_type in {"CIKIS", "FIRE", "DUZELTME_EKSI"}
    with transaction.atomic():
        material = Material.objects.select_for_update().get(pk=material.pk)
        stock, _ = MaterialWarehouseStock.objects.select_for_update().get_or_create(material=material, warehouse=warehouse, renk=renk, defaults={"miktar": 0})
        before = stock.miktar
        after = before - amount if negative else before + amount
        if after < 0:
            messages.error(request, "Stok miktarı eksiye düşemez."); return redirect("inventory_warehouse_detail", code=code)
        stock.miktar = after; stock.save(update_fields=["miktar", "updated_at"]); material.sync_total_stock()
        MaterialStockMovement.objects.create(material=material, warehouse=warehouse, renk=renk, movement_type=movement_type, miktar=amount, onceki_stok=before, sonraki_stok=after, aciklama=(request.POST.get("note") or "").strip(), islem_yapan=request.user)
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


_CANCEL_PREFIX = "[Stok iptali #"


def _is_manual_cancelable(movement):
    return (not movement.reversed and not movement.order_id and not movement.source_event_id
            and movement.movement_type in {"GIRIS", "CIKIS", "IADE", "FIRE", "DUZELTME_ARTI", "DUZELTME_EKSI", "BASLANGIC"}
            and not movement.aciklama.startswith(_CANCEL_PREFIX))


@login_required
def cancel_material_movement(request, code, material_id, movement_id):
    if request.method != "POST" or not _can_cancel_movement(request.user):
        return HttpResponseForbidden("Bu işlem için yetkiniz yok.")
    warehouse = get_object_or_404(Warehouse, kod=code, aktif=True)
    with transaction.atomic():
        material = get_object_or_404(Material.objects.select_for_update(), pk=material_id, aktif=True)
        movement = get_object_or_404(MaterialStockMovement.objects.select_for_update(),
                                     pk=movement_id, material=material, warehouse=warehouse)
        if not _is_manual_cancelable(movement):
            messages.error(request, "Bu hareket iptal edilemez.")
            return redirect("inventory_material_card", code=code, material_id=material_id)
        stock = get_object_or_404(MaterialWarehouseStock.objects.select_for_update(),
                                  material=material, warehouse=warehouse, renk=movement.renk)
        before = stock.miktar
        after = before - movement.signed_amount
        if after < 0:
            messages.error(request, "İptal sonucunda stok eksiye düşeceği için işlem yapılamadı.")
            return redirect("inventory_material_card", code=code, material_id=material_id)
        stock.miktar = after
        stock.save(update_fields=["miktar", "updated_at"])
        material.sync_total_stock()
        MaterialStockMovement.objects.create(
            material=material, warehouse=warehouse, renk=movement.renk,
            movement_type="DUZELTME_EKSI" if movement.signed_amount > 0 else "DUZELTME_ARTI",
            miktar=movement.miktar, onceki_stok=before, sonraki_stok=after,
            aciklama=f"{_CANCEL_PREFIX}{movement.pk}] {movement.get_movement_type_display()} geri alındı.",
            islem_yapan=request.user,
        )
        movement.reversed = True
        movement.save(update_fields=["reversed"])
    messages.success(request, "Stok hareketi iptal edildi ve stok miktarı güncellendi.")
    return redirect("inventory_material_card", code=code, material_id=material_id)
