from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .customer_report_views import _can_view
from .models import Musteri


@login_required
def customer_list(request):
    if not _can_view(request.user):
        return HttpResponseForbidden("Müşterileri görme yetkiniz yok.")

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
