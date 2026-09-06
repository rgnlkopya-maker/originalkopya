from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import (
    Beden,
    Musteri,
    Order,
    OrderImage,
    ProductCost,
    Renk,
    URUN_TIPI_CHOICES,
    UrunKod,
)


def _to_decimal(value):
    if value in [None, "", "None"]:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


@login_required
def order_multi_create(request):
    if request.method == "POST":
        urun_kodu = (request.POST.get("urun_kodu") or "").strip().upper()
        urun_tipi = (request.POST.get("urun_tipi") or "").strip()
        musteri_id = request.POST.get("musteri")
        siparis_tipi = request.POST.get("siparis_tipi") or None
        teslim_tarihi = request.POST.get("teslim_tarihi") or None
        aciklama = request.POST.get("aciklama")
        musteri = Musteri.objects.filter(id=musteri_id).first()

        satis_fiyati = _to_decimal(request.POST.get("satis_fiyati")) or Decimal("0")
        maliyet_uygulanan = _to_decimal(request.POST.get("maliyet_uygulanan")) or Decimal("0")
        maliyet_override = _to_decimal(request.POST.get("maliyet_override"))
        ekstra_maliyet = _to_decimal(request.POST.get("ekstra_maliyet")) or Decimal("0")
        para_birimi = request.POST.get("para_birimi") or "TRY"
        maliyet_para_birimi = request.POST.get("maliyet_para_birimi") or "TRY"

        if maliyet_uygulanan == 0 and urun_kodu:
            pc = ProductCost.objects.filter(urun_kodu__iexact=urun_kodu).first()
            if pc:
                maliyet_uygulanan = pc.maliyet or Decimal("0")
                maliyet_para_birimi = pc.para_birimi or "TRY"

        uploaded_images = request.FILES.getlist("order_images")
        created_orders = []

        row_indices = set()
        for key in request.POST.keys():
            if key.startswith("renk_row_"):
                index = key.replace("renk_row_", "")
                if index.isdigit():
                    row_indices.add(int(index))

        for i in sorted(row_indices):
            renk = request.POST.get(f"renk_row_{i}")
            bedenler = request.POST.getlist(f"beden_row_{i}[]")
            musteri_ref = request.POST.get(f"musteri_ref_row_{i}", "").strip()
            if not renk or not bedenler:
                continue

            try:
                adet_input = max(1, int(request.POST.get(f"adet_row_{i}") or 1))
            except Exception:
                adet_input = 1

            for beden in bedenler:
                for _ in range(adet_input):
                    order = Order.objects.create(
                        siparis_tipi=siparis_tipi,
                        musteri=musteri,
                        urun_kodu=urun_kodu,
                        urun_tipi=urun_tipi,
                        renk=renk,
                        beden=beden,
                        adet=1,
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

        if uploaded_images and created_orders:
            for order in created_orders:
                for image in uploaded_images:
                    try:
                        image.seek(0)
                        OrderImage.objects.create(order=order, image=image)
                    except Exception as exc:
                        messages.warning(request, f"{image.name} görseli yüklenemedi: {exc}")

        if created_orders:
            if uploaded_images:
                messages.success(
                    request,
                    f"{len(created_orders)} sipariş oluşturuldu; seçilen {len(uploaded_images)} görsel siparişlere eklendi.",
                )
            else:
                messages.success(request, f"{len(created_orders)} adet sipariş başarıyla oluşturuldu!")
        else:
            messages.warning(request, "Oluşturulacak geçerli sipariş satırı bulunamadı.")
        return redirect("order_list")

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
