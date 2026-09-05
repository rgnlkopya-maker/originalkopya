from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Min, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Musteri, Order


def _can_view(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _money_buckets(queryset):
    revenue = {"TRY": Decimal("0"), "USD": Decimal("0"), "EUR": Decimal("0")}
    cost = {"TRY": Decimal("0"), "USD": Decimal("0"), "EUR": Decimal("0")}
    profit = {"TRY": Decimal("0"), "USD": Decimal("0"), "EUR": Decimal("0")}

    for order in queryset.only(
        "satis_fiyati", "para_birimi", "maliyet_override", "maliyet_uygulanan",
        "maliyet_para_birimi", "ekstra_maliyet"
    ):
        sale_currency = order.para_birimi or "TRY"
        cost_currency = order.maliyet_para_birimi or "TRY"
        sale = Decimal(order.satis_fiyati or 0)
        base_cost = Decimal(order.maliyet_override if order.maliyet_override is not None else (order.maliyet_uygulanan or 0))
        total_cost = base_cost + Decimal(order.ekstra_maliyet or 0)

        if sale_currency in revenue:
            revenue[sale_currency] += sale
        if cost_currency in cost:
            cost[cost_currency] += total_cost
        if sale_currency == cost_currency and sale_currency in profit:
            profit[sale_currency] += sale - total_cost

    return revenue, cost, profit


@login_required
def customer_comparison_report(request):
    if not _can_view(request.user):
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
        ilk_siparis=Min("order__siparis_tarihi", filter=Q(order__in=orders)),
        son_siparis=Max("order__siparis_tarihi", filter=Q(order__in=orders)),
    )

    rows = []
    total_orders = 0
    active_90 = 0
    for customer in customers:
        cq = orders.filter(musteri=customer)
        revenue, cost, profit = _money_buckets(cq)
        top_product = cq.exclude(urun_kodu__isnull=True).exclude(urun_kodu="").values("urun_kodu").annotate(total=Count("id")).order_by("-total").first()
        last_days = (today - customer.son_siparis).days if customer.son_siparis else None
        status = "aktif" if last_days is not None and last_days <= 90 else ("dikkat" if last_days is not None and last_days <= 180 else "pasif")
        if status == "aktif":
            active_90 += 1
        total_orders += customer.siparis_sayisi or 0

        rows.append({
            "id": customer.id,
            "ad": customer.ad,
            "siparis": customer.siparis_sayisi or 0,
            "ozel": cq.filter(siparis_tipi="OZEL").count(),
            "tekli": cq.filter(siparis_tipi="TEKLI").count(),
            "seri": cq.filter(siparis_tipi="SERI").count(),
            "ilk": customer.ilk_siparis,
            "son": customer.son_siparis,
            "gun": last_days,
            "status": status,
            "top_product": top_product["urun_kodu"] if top_product else "—",
            "try_total": revenue["TRY"], "usd_total": revenue["USD"], "eur_total": revenue["EUR"],
            "cost_try": cost["TRY"], "cost_usd": cost["USD"], "cost_eur": cost["EUR"],
            "profit_try": profit["TRY"], "profit_usd": profit["USD"], "profit_eur": profit["EUR"],
            "revenue_sort": float(revenue["TRY"] + revenue["USD"] + revenue["EUR"]),
            "cost_sort": float(cost["TRY"] + cost["USD"] + cost["EUR"]),
            "profit_sort": float(profit["TRY"] + profit["USD"] + profit["EUR"]),
        })

    rows.sort(key=lambda x: x["siparis"], reverse=True)

    return render(request, "reports/customer_comparison.html", {
        "rows": rows,
        "customer_count": len(rows),
        "total_orders": total_orders,
        "active_90": active_90,
        "start": start,
        "end": end,
        "q": q,
    })


@login_required
def customer_detail_report(request, customer_id):
    if not _can_view(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Bu raporu görme yetkiniz yok.")

    customer = get_object_or_404(Musteri, pk=customer_id)
    orders = Order.objects.filter(musteri=customer, is_active=True).exclude(siparis_tipi="STOK").order_by("-siparis_tarihi", "-id")
    revenue, cost, profit = _money_buckets(orders)
    top_products = orders.exclude(urun_kodu__isnull=True).exclude(urun_kodu="").values("urun_kodu").annotate(total=Count("id")).order_by("-total")[:10]

    return render(request, "reports/customer_detail.html", {
        "customer": customer,
        "orders": orders,
        "order_count": orders.count(),
        "ozel_count": orders.filter(siparis_tipi="OZEL").count(),
        "tekli_count": orders.filter(siparis_tipi="TEKLI").count(),
        "seri_count": orders.filter(siparis_tipi="SERI").count(),
        "first_order": orders.aggregate(v=Min("siparis_tarihi"))["v"],
        "last_order": orders.aggregate(v=Max("siparis_tarihi"))["v"],
        "top_products": top_products,
        "revenue": revenue,
        "cost": cost,
        "profit": profit,
    })
