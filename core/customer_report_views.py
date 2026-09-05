from collections import Counter, defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import DateTimeField, OuterRef, Subquery
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from product_cards.finance_views import calculate_finance_result
from .models import Musteri, Order, OrderEvent


def _can_view(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _shipment_finance_rows(start="", end="", customer_query="", customer_id=None):
    """Use the exact same row-selection rule as Sevkiyat Finans Tablosu."""
    finance_stages = [
        "satis_fiyati",
        "ekstra_maliyet",
        "maliyet_override",
        "maliyet_uygulanan",
    ]
    latest_event = (
        OrderEvent.objects
        .filter(order=OuterRef("pk"))
        .exclude(event_type="order_update")
        .exclude(stage__in=finance_stages)
        .order_by("-id")[:1]
    )
    qs = (
        Order.objects
        .select_related("musteri")
        .annotate(
            latest_stage=Subquery(latest_event.values("stage")),
            latest_value=Subquery(latest_event.values("value")),
            last_status_date=Subquery(latest_event.values("timestamp"), output_field=DateTimeField()),
        )
        .filter(
            is_active=True,
            musteri__isnull=False,
            latest_stage="sevkiyat_durum",
            latest_value="gonderildi",
        )
        .order_by("-id")
    )
    if start:
        qs = qs.filter(last_status_date__date__gte=start)
    if end:
        qs = qs.filter(last_status_date__date__lte=end)
    if customer_query:
        qs = qs.filter(musteri__ad__icontains=customer_query)
    if customer_id is not None:
        qs = qs.filter(musteri_id=customer_id)

    rows = []
    for order in qs:
        result = calculate_finance_result(order)
        rows.append({
            "order": order,
            "result": result,
            "ship_date": timezone.localtime(order.last_status_date).date() if order.last_status_date else None,
        })
    return rows


@login_required
def customer_comparison_report(request):
    if not _can_view(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Bu raporu görme yetkiniz yok.")

    today = timezone.localdate()
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    q = (request.GET.get("q") or "").strip()
    finance_rows = _shipment_finance_rows(start=start, end=end, customer_query=q)

    grouped = defaultdict(list)
    for item in finance_rows:
        grouped[item["order"].musteri_id].append(item)

    customers = Musteri.objects.in_bulk(grouped.keys())
    rows = []
    total_orders = 0
    active_90 = 0

    for customer_id, items in grouped.items():
        customer = customers.get(customer_id)
        if not customer:
            continue

        dated = [x for x in items if x["ship_date"]]
        dated.sort(key=lambda x: (x["ship_date"], x["order"].id))
        first_date = dated[0]["ship_date"] if dated else None
        last_date = dated[-1]["ship_date"] if dated else None
        last_days = (today - last_date).days if last_date else None
        status = "aktif" if last_days is not None and last_days <= 90 else ("dikkat" if last_days is not None and last_days <= 180 else "pasif")
        if status == "aktif":
            active_90 += 1

        type_counts = Counter((x["order"].siparis_tipi or "") for x in items)
        product_counts = Counter((x["order"].urun_kodu or "") for x in items if x["order"].urun_kodu)
        top_product = product_counts.most_common(1)[0][0] if product_counts else "—"

        # Sevkiyat Finans ekranindaki ust toplamlarla ayni: yalnizca is_final satirlar finans toplamlarina girer.
        final_items = [x for x in items if x["result"].get("is_final")]
        revenue_tl = sum((Decimal(x["result"]["satis_tl"] or 0) for x in final_items), Decimal("0"))
        cost_tl = sum((Decimal(x["result"]["maliyet_tl"] or 0) for x in final_items), Decimal("0"))
        profit_tl = sum((Decimal(x["result"]["kar_tl"] or 0) for x in final_items), Decimal("0"))

        count = len(items)
        total_orders += count
        rows.append({
            "id": customer.id,
            "ad": customer.ad,
            "siparis": count,
            "ozel": type_counts.get("OZEL", 0),
            "tekli": type_counts.get("TEKLI", 0),
            "seri": type_counts.get("SERI", 0),
            "ilk": first_date,
            "son": last_date,
            "gun": last_days,
            "status": status,
            "top_product": top_product,
            "try_total": revenue_tl,
            "usd_total": Decimal("0"),
            "eur_total": Decimal("0"),
            "cost_try": cost_tl,
            "cost_usd": Decimal("0"),
            "cost_eur": Decimal("0"),
            "profit_try": profit_tl,
            "profit_usd": Decimal("0"),
            "profit_eur": Decimal("0"),
            "revenue_sort": float(revenue_tl),
            "cost_sort": float(cost_tl),
            "profit_sort": float(profit_tl),
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
    finance_rows = _shipment_finance_rows(customer_id=customer.id)
    finance_rows.sort(key=lambda x: ((x["ship_date"] or timezone.localdate()), x["order"].id), reverse=True)
    orders = [x["order"] for x in finance_rows]

    type_counts = Counter((o.siparis_tipi or "") for o in orders)
    product_counts = Counter((o.urun_kodu or "") for o in orders if o.urun_kodu)
    top_products = [{"urun_kodu": code, "total": total} for code, total in product_counts.most_common(10)]

    final_items = [x for x in finance_rows if x["result"].get("is_final")]
    revenue_tl = sum((Decimal(x["result"]["satis_tl"] or 0) for x in final_items), Decimal("0"))
    cost_tl = sum((Decimal(x["result"]["maliyet_tl"] or 0) for x in final_items), Decimal("0"))
    profit_tl = sum((Decimal(x["result"]["kar_tl"] or 0) for x in final_items), Decimal("0"))

    dated = [x for x in finance_rows if x["ship_date"]]
    dates = [x["ship_date"] for x in dated]
    return render(request, "reports/customer_detail.html", {
        "customer": customer,
        "orders": orders,
        "order_count": len(orders),
        "ozel_count": type_counts.get("OZEL", 0),
        "tekli_count": type_counts.get("TEKLI", 0),
        "seri_count": type_counts.get("SERI", 0),
        "first_order": min(dates) if dates else None,
        "last_order": max(dates) if dates else None,
        "top_products": top_products,
        "revenue": {"TRY": revenue_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "cost": {"TRY": cost_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "profit": {"TRY": profit_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
    })
