from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app_settings.access import has_feature_access, order_scope_allows
from core.models import Order
from .models import SerialCutPlan


def _can_edit(user):
    return has_feature_access(user, "planning.edit_calendar")


@login_required
def serial_cutting_page(request):
    raw = request.GET.get("date")
    try:
        selected = date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        selected = date.today()
    monday = selected - timedelta(days=selected.weekday())
    weekdays = [monday + timedelta(days=i) for i in range(5)]
    plans = SerialCutPlan.objects.filter(planned_date__range=(monday, weekdays[-1])).select_related("order")
    grouped = {day.isoformat(): {} for day in weekdays}
    for plan in plans:
        order = plan.order
        if not order_scope_allows(request.user, order):
            continue
        key = (order.urun_kodu or "", order.renk or "", order.beden or "")
        bucket = grouped[plan.planned_date.isoformat()].setdefault(key, {
            "product": key[0], "color": key[1], "size": key[2], "quantity": 0, "order_ids": [], "plans": []
        })
        bucket["quantity"] += plan.quantity
        bucket["order_ids"].append(order.id)
        bucket["plans"].append(plan)
    columns = []
    week_total = 0
    for day in weekdays:
        rows = sorted(grouped[day.isoformat()].values(), key=lambda r: (r["product"], r["color"], r["size"]))
        total = sum(row["quantity"] for row in rows)
        week_total += total
        products = defaultdict(int)
        for row in rows:
            products[row["product"]] += row["quantity"]
        columns.append({"date": day, "rows": rows, "total": total, "products": sorted(products.items())})
    orders = Order.objects.filter(is_active=True).exclude(siparis_tipi="MALZEME").order_by("-id")[:1500]
    orders = [order for order in orders if order_scope_allows(request.user, order)]
    return render(request, "planning/serial_cutting.html", {
        "columns": columns, "week_total": week_total, "orders": orders,
        "can_edit": _can_edit(request.user),
        "prev_date": (monday-timedelta(days=7)).isoformat(),
        "next_date": (monday+timedelta(days=7)).isoformat(),
    })


@login_required
@require_POST
def serial_cutting_add(request):
    if not _can_edit(request.user):
        return HttpResponseForbidden("Planlama yetkiniz yok.")
    order = get_object_or_404(Order, pk=request.POST.get("order_id"), is_active=True)
    if not order_scope_allows(request.user, order):
        return HttpResponseForbidden("Sipariş yetkiniz yok.")
    try:
        day = date.fromisoformat(request.POST.get("planned_date", ""))
        quantity = int(request.POST.get("quantity", ""))
    except (ValueError, TypeError):
        return HttpResponseForbidden("Geçersiz tarih veya adet.")
    if day.weekday() > 4 or quantity < 1:
        return HttpResponseForbidden("Yalnızca hafta içi ve pozitif adet girilebilir.")
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        existing = SerialCutPlan.objects.select_for_update().filter(order=order)
        allocated = sum(item.quantity for item in existing)
        if quantity + allocated > (order.adet or 0):
            return HttpResponseForbidden("Planlanan toplam adet sipariş adedini aşamaz.")
        plan = existing.filter(planned_date=day).first()
        if plan:
            plan.quantity += quantity
            plan.save(update_fields=["quantity"])
        else:
            SerialCutPlan.objects.create(order=order, planned_date=day, quantity=quantity, created_by=request.user)
    return redirect(f"{reverse('serial_cutting_page')}?date={day.isoformat()}")


@login_required
@require_POST
def serial_cutting_remove(request, plan_id):
    if not _can_edit(request.user):
        return HttpResponseForbidden("Planlama yetkiniz yok.")
    plan = get_object_or_404(SerialCutPlan, pk=plan_id)
    if not order_scope_allows(request.user, plan.order):
        return HttpResponseForbidden("Sipariş yetkiniz yok.")
    day = plan.planned_date
    plan.delete()
    return redirect(f"{reverse('serial_cutting_page')}?date={day.isoformat()}")
