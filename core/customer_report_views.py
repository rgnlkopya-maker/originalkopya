from collections import Counter, defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from product_cards.finance_views import calculate_finance_result
from product_cards.models import ShipmentFinancialSnapshot
from .models import Musteri


def _can_view(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


def _valid_shipment_rows(start="", end="", customer_query="", customer_id=None):
    """Return exactly the currently valid shipped orders used by shipment finance logic.

    A row is included only when it has a shipment snapshot and the live finance equation
    says the shipment is currently a final SEVKEDILDI state. Returns / wrong shipment /
    cargo-return rows therefore disappear automatically; a re-shipment appears again.
    Financial movements are recalculated on every request.
    """
    snapshots = ShipmentFinancialSnapshot.objects.select_related("order", "order__musteri").filter(
        order__musteri__isnull=False,
        order__is_active=True,
    )
    if start:
        snapshots = snapshots.filter(created_at__date__gte=start)
    if end:
        snapshots = snapshots.filter(created_at__date__lte=end)
    if customer_query:
        snapshots = snapshots.filter(order__musteri__ad__icontains=customer_query)
    if customer_id is not None:
        snapshots = snapshots.filter(order__musteri_id=customer_id)

    valid = []
    for snapshot in snapshots.order_by("created_at", "id"):
        order = snapshot.order
        result = calculate_finance_result(order)
        if result.get("status") != "SEVKEDILDI" or not result.get("is_final"):
            continue
        valid.append({
            "order": order,
            "snapshot": snapshot,
            "result": result,
            "ship_date": timezone.localtime(snapshot.created_at).date(),
        })
    return valid


@login_required
def customer_comparison_report(request):
    if not _can_view(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Bu raporu görme yetkiniz yok.")

    today = timezone.localdate()
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    q = (request.GET.get("q") or "").strip()
    valid = _valid_shipment_rows(start=start, end=end, customer_query=q)

    grouped = defaultdict(list)
    for item in valid:
        grouped[item["order"].musteri_id].append(item)

    customers = Musteri.objects.in_bulk(grouped.keys())
    rows = []
    total_orders = 0
    active_90 = 0

    for customer_id, items in grouped.items():
        customer = customers.get(customer_id)
        if not customer:
            continue

        items.sort(key=lambda x: (x["ship_date"], x["order"].id))
        first_date = items[0]["ship_date"]
        last_date = items[-1]["ship_date"]
        last_days = (today - last_date).days
        status = "aktif" if last_days <= 90 else ("dikkat" if last_days <= 180 else "pasif")
        if status == "aktif":
            active_90 += 1

        type_counts = Counter((x["order"].siparis_tipi or "") for x in items)
        product_counts = Counter((x["order"].urun_kodu or "") for x in items if x["order"].urun_kodu)
        top_product = product_counts.most_common(1)[0][0] if product_counts else "—"

        revenue_tl = sum((Decimal(x["result"]["satis_tl"] or 0) for x in items), Decimal("0"))
        cost_tl = sum((Decimal(x["result"]["maliyet_tl"] or 0) for x in items), Decimal("0"))
        profit_tl = sum((Decimal(x["result"]["kar_tl"] or 0) for x in items), Decimal("0"))

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
    valid = _valid_shipment_rows(customer_id=customer.id)
    valid.sort(key=lambda x: (x["ship_date"], x["order"].id), reverse=True)

    orders = [x["order"] for x in valid]
    type_counts = Counter((o.siparis_tipi or "") for o in orders)
    product_counts = Counter((o.urun_kodu or "") for o in orders if o.urun_kodu)
    top_products = [{"urun_kodu": code, "total": total} for code, total in product_counts.most_common(10)]

    revenue_tl = sum((Decimal(x["result"]["satis_tl"] or 0) for x in valid), Decimal("0"))
    cost_tl = sum((Decimal(x["result"]["maliyet_tl"] or 0) for x in valid), Decimal("0"))
    profit_tl = sum((Decimal(x["result"]["kar_tl"] or 0) for x in valid), Decimal("0"))

    return render(request, "reports/customer_detail.html", {
        "customer": customer,
        "orders": orders,
        "order_count": len(orders),
        "ozel_count": type_counts.get("OZEL", 0),
        "tekli_count": type_counts.get("TEKLI", 0),
        "seri_count": type_counts.get("SERI", 0),
        "first_order": valid[-1]["ship_date"] if valid else None,
        "last_order": valid[0]["ship_date"] if valid else None,
        "top_products": top_products,
        "revenue": {"TRY": revenue_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "cost": {"TRY": cost_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "profit": {"TRY": profit_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
    })
