"""Product performance report based on the same finalized shipment finance rows."""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from app_settings.access import has_access

from .customer_report_views import _shipment_finance_rows
from .models import URUN_TIPI_CHOICES


ZERO = Decimal("0")


def _valid_date(value):
    if not value:
        return ""
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return ""


def build_product_summary(finance_rows, *, query="", product_type=""):
    """Group only shipped orders; maintain distinct order and actual unit counts.

    Monetary totals intentionally use calculate_finance_result through the shared
    shipment helper, so adjustments in Sevkiyat Finans are reflected on refresh.
    """
    grouped = {}
    search = (query or "").strip().casefold()

    for item in finance_rows:
        order = item["order"]
        code = (order.urun_kodu or "").strip().upper() or "BELİRTİLMEMİŞ"
        kind = order.urun_tipi or ""
        if product_type and kind != product_type:
            continue
        if search and search not in code.casefold():
            continue

        bucket = grouped.setdefault(code, {
            "code": code, "types": Counter(), "orders": 0, "quantity": 0,
            "ozel": 0, "tekli": 0, "seri": 0,
            "customers": Counter(), "colors": Counter(),
            "revenue": ZERO, "cost": ZERO, "profit": ZERO,
            "finance_missing": 0, "first": None, "last": None,
        })
        qty = order.adet if order.adet is not None else 1
        bucket["orders"] += 1
        bucket["quantity"] += qty
        bucket["types"][kind] += 1
        if order.siparis_tipi == "OZEL":
            bucket["ozel"] += 1
        elif order.siparis_tipi == "TEKLI":
            bucket["tekli"] += 1
        elif order.siparis_tipi == "SERI":
            bucket["seri"] += 1
        if order.musteri_id:
            label = order.musteri.ad if order.musteri else "Bilinmiyor"
            bucket["customers"][label] += qty
        if order.renk:
            bucket["colors"][order.renk.strip().upper()] += qty

        shipped = item["ship_date"]
        if shipped:
            if bucket["first"] is None or shipped < bucket["first"]:
                bucket["first"] = shipped
            if bucket["last"] is None or shipped > bucket["last"]:
                bucket["last"] = shipped

        result = item["result"]
        snapshot = result.get("snapshot")
        if snapshot is None or snapshot.toplam_maliyet_tl is None:
            # A missing cost is not proof of zero cost: display a warning.
            bucket["finance_missing"] += 1
        if result.get("is_final"):
            bucket["revenue"] += Decimal(result.get("satis_tl") or 0)
            bucket["cost"] += Decimal(result.get("maliyet_tl") or 0)
            bucket["profit"] += Decimal(result.get("kar_tl") or 0)

    rows = []
    totals = {
        "products": len(grouped), "orders": 0, "quantity": 0,
        "revenue": ZERO, "cost": ZERO, "profit": ZERO, "finance_missing": 0,
    }
    type_labels = dict(URUN_TIPI_CHOICES)
    for bucket in grouped.values():
        kind = bucket["types"].most_common(1)[0][0] if bucket["types"] else ""
        margin = (bucket["profit"] / bucket["revenue"] * 100) if bucket["revenue"] else None
        avg_price = (bucket["revenue"] / bucket["quantity"]) if bucket["quantity"] else None
        customer = bucket["customers"].most_common(1)[0] if bucket["customers"] else ("—", 0)
        color = bucket["colors"].most_common(1)[0] if bucket["colors"] else ("—", 0)
        row = {
            **bucket,
            "type_label": type_labels.get(kind, "Belirtilmemiş"),
            "customer_count": len(bucket["customers"]),
            "top_customer": customer[0],
            "top_customer_units": customer[1],
            "top_color": color[0],
            "top_color_units": color[1],
            "margin": margin,
            "avg_price": avg_price,
            "in_loss": bucket["profit"] < 0,
        }
        rows.append(row)
        for field in ("orders", "quantity", "revenue", "cost", "profit", "finance_missing"):
            totals[field] += bucket[field]
    rows.sort(key=lambda row: (-row["quantity"], -row["revenue"], row["code"]))
    totals["margin"] = totals["profit"] / totals["revenue"] * 100 if totals["revenue"] else None
    return rows, totals


@login_required
def product_performance_report(request):
    if not has_access(request.user, "can_view_reports"):
        return HttpResponseForbidden("Ürün raporunu görme yetkiniz yok.")

    query = (request.GET.get("q") or "").strip()[:100]
    start = _valid_date(request.GET.get("start"))
    end = _valid_date(request.GET.get("end"))
    product_type = request.GET.get("type") or ""
    types = dict(URUN_TIPI_CHOICES)
    if product_type not in types:
        product_type = ""

    finance_rows = _shipment_finance_rows(start=start, end=end)
    rows, totals = build_product_summary(finance_rows, query=query, product_type=product_type)
    return render(request, "reports/product_performance.html", {
        "rows": rows, "totals": totals, "q": query,
        "start": start, "end": end, "selected_type": product_type,
        "product_types": URUN_TIPI_CHOICES,
    })
