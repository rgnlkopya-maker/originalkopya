from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .customer_report_views import _can_view
from .customer_models import CustomerDetail
from .models import Musteri


DETAIL_FIELDS = (
    "yetkili_kisi", "telefon", "telefon_2", "email", "ulke", "adres",
    "teslimat_adresi", "fatura_adresi", "dis_ticaret_firmasi", "notlar",
)


def _find_customer_by_name(name):
    return Musteri.objects.filter(ad__iexact=name).order_by("id").first()


def _save_customer_detail(detail, post):
    for field in DETAIL_FIELDS:
        setattr(detail, field, (post.get(field) or "").strip())
    detail.save()


@login_required
def customer_list(request):
    if not _can_view(request.user):
        return HttpResponseForbidden("Müşterileri görme yetkiniz yok.")

    if request.method == "POST":
        ad = (request.POST.get("ad") or "").strip()
        if not ad:
            messages.error(request, "Müşteri / firma adı boş olamaz.")
            return redirect("customer_list")

        customer = _find_customer_by_name(ad)
        created = False
        reactivated = False

        if customer:
            if customer.aktif:
                messages.warning(
                    request,
                    f"{customer.ad} zaten kayıtlı. Yeni kayıt oluşturulmadı; mevcut müşteri kartı açıldı.",
                )
                return redirect("customer_detail_report", customer_id=customer.id)
            customer.aktif = True
            customer.ad = ad
            customer.save(update_fields=["aktif", "ad"])
            reactivated = True
        else:
            customer = Musteri.objects.create(ad=ad, aktif=True)
            created = True

        detail, _ = CustomerDetail.objects.get_or_create(customer=customer)
        _save_customer_detail(detail, request.POST)

        if reactivated:
            messages.success(request, "Pasif müşteri yeniden aktif edildi ve bilgileri güncellendi.")
        elif created:
            messages.success(request, "Yeni müşteri kaydedildi.")

        return redirect("customer_detail_report", customer_id=customer.id)

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("durum") or "aktif").strip()

    customers = Musteri.objects.all().order_by("ad")
    if q:
        customers = customers.filter(ad__icontains=q)
    if status == "aktif":
        customers = customers.filter(aktif=True)
    elif status == "pasif":
        customers = customers.filter(aktif=False)

    return render(request, "customers/customer_list.html", {
        "customers": customers,
        "q": q,
        "status": status,
        "active_count": Musteri.objects.filter(aktif=True).count(),
        "passive_count": Musteri.objects.filter(aktif=False).count(),
    })


@login_required
def customer_edit(request, customer_id):
    if not _can_view(request.user):
        return HttpResponseForbidden("Müşteri bilgilerini düzenleme yetkiniz yok.")

    customer = get_object_or_404(Musteri, pk=customer_id)
    detail, _ = CustomerDetail.objects.get_or_create(customer=customer)

    if request.method == "POST":
        new_name = (request.POST.get("ad") or "").strip() or customer.ad
        duplicate = Musteri.objects.filter(ad__iexact=new_name).exclude(pk=customer.pk).first()
        if duplicate:
            messages.error(request, "Bu isimde başka bir müşteri zaten kayıtlı.")
            return redirect("customer_edit", customer_id=customer.id)

        customer.ad = new_name
        customer.aktif = request.POST.get("aktif") == "on"
        customer.save(update_fields=["ad", "aktif"])

        _save_customer_detail(detail, request.POST)
        messages.success(request, "Müşteri bilgileri kaydedildi.")
        return redirect("customer_detail_report", customer_id=customer.id)

    return render(request, "customers/customer_edit.html", {
        "customer": customer,
        "detail": detail,
    })
