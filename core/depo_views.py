import re
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Sum
from django.shortcuts import redirect, render

from product_cards.models import MaterialStockMovement, MaterialWarehouseStock, Warehouse
from inventory.models import ProductStockMovement, ProductWarehouseStock


def _normalize_code(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return value[:20] or "DEPO"


@login_required
def depo_ozet(request):
    can_manage = request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()
    if request.method == "POST" and request.POST.get("action") == "add_depot":
        if not can_manage:
            messages.error(request, "Yeni depo ekleme yetkiniz yok."); return redirect("depo_ozet")
        name = (request.POST.get("depo_adi") or "").strip()
        if not name:
            messages.error(request, "Depo adı boş bırakılamaz."); return redirect("depo_ozet")
        code = _normalize_code(name); base = code; i = 2
        while Warehouse.objects.filter(kod=code).exists():
            code = f"{base[:17]}_{i}"[:20]; i += 1
        Warehouse.objects.create(kod=code, ad=name, aktif=True)
        messages.success(request, f"{name} deposu eklendi."); return redirect("depo_ozet")

    depolar = []
    for warehouse in Warehouse.objects.filter(aktif=True).order_by("ad"):
        material_qs = MaterialWarehouseStock.objects.filter(warehouse=warehouse, miktar__gt=0)
        product_qs = ProductWarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0)
        last_material = MaterialStockMovement.objects.filter(warehouse=warehouse).aggregate(v=Max("created_at"))["v"]
        last_product = ProductStockMovement.objects.filter(warehouse=warehouse).aggregate(v=Max("created_at"))["v"]
        last_update = max([d for d in [last_material, last_product] if d], default=None)
        depolar.append({
            "depo": warehouse.kod,
            "depo_adi": warehouse.ad,
            "toplam_adet": product_qs.aggregate(v=Sum("quantity"))["v"] or 0,
            "kayit_sayisi": material_qs.count() + product_qs.count(),
            "son_guncelleme": last_update,
        })
    return render(request, "depolar/ozet.html", {"depolar": depolar, "can_manage_depots": can_manage})
