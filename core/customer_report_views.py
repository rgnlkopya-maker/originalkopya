from collections import Counter, defaultdict
from decimal import Decimal
import json

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
    start = request.GET.get("start") or ""
    end = request.GET.get("end") or ""
    finance_rows = _shipment_finance_rows(start=start, end=end, customer_id=customer.id)
    finance_rows.sort(key=lambda x: ((x["ship_date"] or timezone.localdate()), x["order"].id), reverse=True)
    orders = [x["order"] for x in finance_rows]

    type_counts = Counter((o.siparis_tipi or "") for o in orders)
    product_counts = Counter((o.urun_kodu or "") for o in orders if o.urun_kodu)

    latest_order_by_product = {}
    for item in finance_rows:
        code = item["order"].urun_kodu or ""
        if code and code not in latest_order_by_product:
            latest_order_by_product[code] = item["order"].id
    top_products = [
        {"urun_kodu": code, "total": total, "order_id": latest_order_by_product.get(code)}
        for code, total in product_counts.most_common(10)
    ]

    product_type_counts = Counter()
    for o in orders:
        label = o.get_urun_tipi_display() if getattr(o, "urun_tipi", None) else "Belirtilmemiş"
        product_type_counts[label] += 1
    product_types = [{"label": k, "total": v} for k, v in product_type_counts.most_common()]

    final_items = [x for x in finance_rows if x["result"].get("is_final")]
    revenue_tl = sum((Decimal(x["result"]["satis_tl"] or 0) for x in final_items), Decimal("0"))
    cost_tl = sum((Decimal(x["result"]["maliyet_tl"] or 0) for x in final_items), Decimal("0"))
    profit_tl = sum((Decimal(x["result"]["kar_tl"] or 0) for x in final_items), Decimal("0"))
    profit_margin = (profit_tl / revenue_tl * Decimal("100")) if revenue_tl else Decimal("0")

    product_finance = defaultdict(lambda: {"cost": Decimal("0"), "profit": Decimal("0"), "latest_order_id": None, "latest_key": None})
    for item in final_items:
        code = item["order"].urun_kodu or "Belirtilmemiş"
        bucket = product_finance[code]
        bucket["cost"] += Decimal(item["result"]["maliyet_tl"] or 0)
        bucket["profit"] += Decimal(item["result"]["kar_tl"] or 0)
        key = (item["ship_date"] or timezone.localdate(), item["order"].id)
        if bucket["latest_key"] is None or key > bucket["latest_key"]:
            bucket["latest_key"] = key
            bucket["latest_order_id"] = item["order"].id

    highest_cost_product = None
    highest_profit_product = None
    if product_finance:
        cost_code, cost_data = max(product_finance.items(), key=lambda kv: kv[1]["cost"])
        profit_code, profit_data = max(product_finance.items(), key=lambda kv: kv[1]["profit"])
        highest_cost_product = {
            "urun_kodu": cost_code,
            "value": cost_data["cost"],
            "order_id": cost_data["latest_order_id"],
        }
        highest_profit_product = {
            "urun_kodu": profit_code,
            "value": profit_data["profit"],
            "order_id": profit_data["latest_order_id"],
        }

    dated = [x for x in finance_rows if x["ship_date"]]
    dates = sorted([x["ship_date"] for x in dated])
    first_order = min(dates) if dates else None
    last_order = max(dates) if dates else None
    last_days = (timezone.localdate() - last_order).days if last_order else None
    avg_interval = None
    if len(dates) > 1:
        intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        avg_interval = round(sum(intervals) / len(intervals), 1)

    daily = defaultdict(lambda: {"count": 0, "revenue": Decimal("0"), "profit": Decimal("0")})
    for item in finance_rows:
        if not item["ship_date"]:
            continue
        key = item["ship_date"]
        daily[key]["count"] += 1
        if item["result"].get("is_final"):
            daily[key]["revenue"] += Decimal(item["result"]["satis_tl"] or 0)
            daily[key]["profit"] += Decimal(item["result"]["kar_tl"] or 0)
    day_keys = sorted(daily.keys())
    period_labels = [k.strftime("%d.%m.%Y") for k in day_keys]
    period_counts = [daily[k]["count"] for k in day_keys]
    period_revenue = [float(daily[k]["revenue"]) for k in day_keys]
    period_profit = [float(daily[k]["profit"]) for k in day_keys]

    summary = "Seçilen tarih aralığında sevkiyat bulunamadı."
    if orders:
        summary = f"Seçilen dönemde {len(orders)} ürün sevk edildi."
        if product_counts:
            summary += f" En çok {product_counts.most_common(1)[0][0]} modeli tercih edildi."
        if last_days is not None:
            summary += f" Son sevkiyat {last_days} gün önce yapıldı."

    return render(request, "reports/customer_detail.html", {
        "customer": customer,
        "orders": orders,
        "order_count": len(orders),
        "ozel_count": type_counts.get("OZEL", 0),
        "tekli_count": type_counts.get("TEKLI", 0),
        "seri_count": type_counts.get("SERI", 0),
        "first_order": first_order,
        "last_order": last_order,
        "last_days": last_days,
        "avg_interval": avg_interval,
        "top_products": top_products,
        "highest_cost_product": highest_cost_product,
        "highest_profit_product": highest_profit_product,
        "product_types": product_types,
        "revenue": {"TRY": revenue_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "cost": {"TRY": cost_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "profit": {"TRY": profit_tl, "USD": Decimal("0"), "EUR": Decimal("0")},
        "profit_margin": profit_margin,
        "summary": summary,
        "start": start,
        "end": end,
        "period_labels_json": json.dumps(period_labels, ensure_ascii=False),
        "period_counts_json": json.dumps(period_counts),
        "period_revenue_json": json.dumps(period_revenue),
        "period_profit_json": json.dumps(period_profit),
    })
