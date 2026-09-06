from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import Order


@login_required
def customer_product_price_history(request):
    customer_id = request.GET.get("musteri")
    product_code = (request.GET.get("urun_kodu") or "").strip()

    if not customer_id or not product_code:
        return JsonResponse({"results": []})

    orders = (
        Order.objects.filter(
            musteri_id=customer_id,
            urun_kodu__iexact=product_code,
            sevkiyat_durum="gonderildi",
            satis_fiyati__isnull=False,
        )
        .select_related("musteri")
        .order_by("-sevkiyat_tarihi", "-siparis_tarihi", "-id")[:10]
    )

    results = []
    for order in orders:
        results.append({
            "siparis_numarasi": order.siparis_numarasi,
            "siparis_tarihi": order.siparis_tarihi.strftime("%d.%m.%Y") if order.siparis_tarihi else "-",
            "sevkiyat_tarihi": order.sevkiyat_tarihi.strftime("%d.%m.%Y") if order.sevkiyat_tarihi else "-",
            "urun_kodu": order.urun_kodu or "-",
            "urun_tipi": order.get_urun_tipi_display() if order.urun_tipi else "-",
            "siparis_tipi": order.get_siparis_tipi_display() if order.siparis_tipi else "-",
            "satis_fiyati": str(order.satis_fiyati),
            "para_birimi": order.para_birimi or "TRY",
        })

    return JsonResponse({"results": results})
