from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from core.models import Beden, Musteri, Renk, URUN_TIPI_CHOICES, UrunKod
from .models import PriceListSettings, ProductCard
from .price_list_views import _can_manage, _ensure_price_rates, _price_rows, _real_profit_rate


@login_required
def showroom_page(request):
    if not _can_manage(request.user):
        return HttpResponseForbidden("Bu sayfaya erişim yetkiniz yok.")

    settings = PriceListSettings.get_solo()
    if settings.profit_rate <= 0 and settings.discount_rate > 0:
        settings.discount_rate = Decimal("0")
        settings.save(update_fields=["discount_rate", "updated_at"])

    rate_error = _ensure_price_rates(settings)
    show_inactive = request.GET.get("durum") == "pasif"
    musteriler = Musteri.objects.filter(aktif=True).order_by("ad")
    renkler = Renk.objects.filter(aktif=True).order_by("ad")
    bedenler = Beden.objects.filter(aktif=True).order_by("ad")
    urun_kodlari = UrunKod.objects.filter(aktif=True).order_by("kod")

    return render(request, "product_cards/showroom_page.html", {
        "settings": settings,
        "rows": _price_rows(settings, active=not show_inactive),
        "show_inactive": show_inactive,
        "inactive_count": ProductCard.objects.filter(price_list_active=False).count(),
        "rate_error": rate_error,
        "real_profit_rate": _real_profit_rate(settings.profit_rate, settings.discount_rate),
        "showroom_mode": True,
        "musteriler": musteriler,
        "renkler": renkler,
        "bedenler": bedenler,
        "urun_kodlari": urun_kodlari,
        "aktif_musteriler": musteriler,
        "aktif_renkler": renkler,
        "aktif_bedenler": bedenler,
        "aktif_urun_kodlari": urun_kodlari,
        "urun_tipi_secenekleri": URUN_TIPI_CHOICES,
    })
