from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .customer_models import CustomerDetail
from .models import Beden, Musteri, Renk, URUN_TIPI_CHOICES, UrunKod


CUSTOMER_DETAIL_FIELDS = (
    "yetkili_kisi", "telefon", "telefon_2", "email", "ulke", "adres",
    "teslimat_adresi", "fatura_adresi", "dis_ticaret_firmasi", "notlar",
)


def _reactivate_or_create(model, lookup_field, value, extra_defaults=None):
    extra_defaults = extra_defaults or {}
    lookup = {f"{lookup_field}__iexact": value}
    existing = model.objects.filter(**lookup).order_by("id").first()

    if existing:
        if existing.aktif:
            return existing, False, False
        existing.aktif = True
        for field, field_value in extra_defaults.items():
            setattr(existing, field, field_value)
        existing.save(update_fields=["aktif", *extra_defaults.keys()])
        return existing, False, True

    obj = model.objects.create(**{lookup_field: value, **extra_defaults})
    return obj, True, False


def _save_customer_detail_from_post(customer, post):
    has_detail = any((post.get(field) or "").strip() for field in CUSTOMER_DETAIL_FIELDS)
    if not has_detail:
        return
    detail, _ = CustomerDetail.objects.get_or_create(customer=customer)
    for field in CUSTOMER_DETAIL_FIELDS:
        value = (post.get(field) or "").strip()
        if value:
            setattr(detail, field, value)
    detail.save()


@require_POST
@login_required
def musteri_ekle_veya_aktif_et(request):
    ad = (request.POST.get("ad") or "").strip()
    if not ad:
        return JsonResponse({"success": False, "message": "Müşteri adı boş olamaz."})

    musteri, created, reactivated = _reactivate_or_create(Musteri, "ad", ad)
    if not created and not reactivated:
        return JsonResponse({
            "success": False,
            "message": "Bu müşteri zaten aktif.",
            "id": musteri.id,
            "ad": musteri.ad,
        })

    _save_customer_detail_from_post(musteri, request.POST)

    return JsonResponse({
        "success": True,
        "id": musteri.id,
        "ad": musteri.ad,
        "reactivated": reactivated,
    })


@require_POST
@login_required
def renk_ekle_veya_aktif_et(request):
    ad = (request.POST.get("ad") or "").strip()
    if not ad:
        return JsonResponse({"success": False, "message": "Renk adı boş olamaz."})

    renk, created, reactivated = _reactivate_or_create(Renk, "ad", ad)
    if not created and not reactivated:
        return JsonResponse({"success": False, "message": "Bu renk zaten aktif."})

    return JsonResponse({
        "success": True,
        "id": renk.id,
        "ad": renk.ad,
        "reactivated": reactivated,
    })


@require_POST
@login_required
def beden_ekle_veya_aktif_et(request):
    ad = (request.POST.get("ad") or "").strip()
    if not ad:
        return JsonResponse({"success": False, "message": "Beden adı boş olamaz."})

    beden, created, reactivated = _reactivate_or_create(Beden, "ad", ad)
    if not created and not reactivated:
        return JsonResponse({"success": False, "message": "Bu beden zaten aktif."})

    return JsonResponse({
        "success": True,
        "id": beden.id,
        "ad": beden.ad,
        "reactivated": reactivated,
    })


@require_POST
@login_required
def urun_kod_ekle_veya_aktif_et(request):
    kod = (request.POST.get("kod") or "").strip().upper()
    urun_tipi = (request.POST.get("urun_tipi") or "").strip()

    if not kod:
        return JsonResponse({"success": False, "message": "Ürün kodu boş olamaz."})

    valid_types = {value for value, _label in URUN_TIPI_CHOICES}
    if urun_tipi not in valid_types:
        return JsonResponse({"success": False, "message": "Geçerli bir ürün tipi seçin."})

    urun, created, reactivated = _reactivate_or_create(
        UrunKod,
        "kod",
        kod,
        {"urun_tipi": urun_tipi},
    )
    if not created and not reactivated:
        return JsonResponse({"success": False, "message": "Bu ürün kodu zaten aktif."})

    return JsonResponse({
        "success": True,
        "id": urun.id,
        "kod": urun.kod,
        "urun_tipi": urun.urun_tipi,
        "reactivated": reactivated,
    })
