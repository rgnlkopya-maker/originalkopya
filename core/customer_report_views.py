from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Min, Sum, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from .models import Musteri, Order


@login_required
def customer_comparison_report(request):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=["patron", "mudur"]).exists()):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Bu raporu görme yetkiniz yok.")

    today = timezone.localdate()
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    q = (request.GET.get("q") or "").strip()

    orders = Order.objects.filter(musteri__isnull=False, is_active=True).exclude(siparis_tipi="STOK")
    if start:
        orders = orders.filter(siparis_tarihi__gte=start)
    if end:
        orders = orders.filter(siparis_tarihi__lte=end)
    if q:
        orders = orders.filter(musteri__ad__icontains=q)

    customer_ids = orders.values_list("musteri_id", flat=True).distinct()
    customers = Musteri.objects.filter(id__in=customer_ids).annotate(
        siparis_sayisi=Count("order", filter=Q(order__in=orders), distinct=True),
        toplam_adet=Coalesce(Sum("order__adet", filter=Q(order__in=orders)), 0),
        ilk_siparis=Min("order__siparis_tarihi", filter=Q(order__in=orders)),
        son_siparis=Max("order__siparis_tarihi", filter=Q(order__in=orders)),
    )

    rows = []
    total_units = 0
    total_orders = 0
    active_90 = 0
    for customer in customers:
        cq = orders.filter(musteri=customer)
        currency_totals = {x["para_birimi"] or "TRY": x["total"] or Decimal("0") for x in cq.values("para_birimi").annotate(total=Sum("satis_fiyati"))}
        top_product = cq.exclude(urun_kodu__isnull=True).exclude(urun_kodu="").values("urun_kodu").annotate(total=Sum("adet")).order_by("-total").first()
        last_days = (today - customer.son_siparis).days if customer.son_siparis else None
        status = "aktif" if last_days is not None and last_days <= 90 else ("dikkat" if last_days is not None and last_days <= 180 else "pasif")
        if status == "aktif": active_90 += 1
        total_units += customer.toplam_adet or 0
        total_orders += customer.siparis_sayisi or 0
        rows.append({
            "id": customer.id, "ad": customer.ad, "siparis": customer.siparis_sayisi or 0,
            "adet": customer.toplam_adet or 0, "ilk": customer.ilk_siparis, "son": customer.son_siparis,
            "gun": last_days, "status": status, "top_product": top_product["urun_kodu"] if top_product else "—",
            "try_total": currency_totals.get("TRY", 0), "usd_total": currency_totals.get("USD", 0), "eur_total": currency_totals.get("EUR", 0),
        })
    rows.sort(key=lambda x: (x["adet"], x["siparis"]), reverse=True)

    return render(request, "reports/customer_comparison.html", {
        "rows": rows, "customer_count": len(rows), "total_units": total_units, "total_orders": total_orders,
        "active_90": active_90, "start": start, "end": end, "q": q,
    })
