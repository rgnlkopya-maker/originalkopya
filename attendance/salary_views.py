from datetime import date
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from app_settings.access import has_full_access
from .models import SalaryProfile, SalaryPeriod, SalaryTransaction

ZERO = Decimal("0.00")
MAX_AMOUNT = Decimal("99999999999.99")


def _amount(raw, positive=False):
    try:
        value = Decimal(str(raw).strip())
        if not value.is_finite() or value < 0 or value > MAX_AMOUNT or (positive and not value):
            raise ValueError
        return value.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Geçerli, sıfırdan küçük olmayan bir tutar girin.")


def _period(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year") or request.POST.get("year") or today.year)
        month = int(request.GET.get("month") or request.POST.get("month") or today.month)
        if not (2020 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    return year, month


def _back(year, month):
    return f"{reverse('salary_dashboard')}?year={year}&month={month}"


def _get_period(user, year, month):
    profile, _ = SalaryProfile.objects.get_or_create(user=user)
    period, _ = SalaryPeriod.objects.get_or_create(
        user=user, year=year, month=month, defaults={"base_net": profile.monthly_net}
    )
    return period


@login_required
@user_passes_test(has_full_access)
def salary_dashboard(request):
    year, month = _period(request)
    employees = User.objects.filter(is_active=True, is_superuser=False).exclude(
        groups__name__iexact="patron"
    ).exclude(groups__name__iexact="mudur").distinct().order_by("first_name", "last_name", "username")
    profiles = {p.user_id: p for p in SalaryProfile.objects.filter(user__in=employees)}
    periods = {p.user_id: p for p in SalaryPeriod.objects.filter(year=year, month=month, user__in=employees).prefetch_related("transactions")}
    rows = []
    total_earned = total_paid = ZERO
    for user in employees:
        profile = profiles.get(user.id)
        period = periods.get(user.id)
        base = period.base_net if period else (profile.monthly_net if profile else ZERO)
        adjustment = period.adjustment if period else ZERO
        deduction = period.deduction if period else ZERO
        earned = base + adjustment - deduction
        paid = period.total_paid if period else ZERO
        rows.append({"user": user, "profile": profile, "period": period, "base": base, "earned": earned,
                     "adjustment": adjustment, "deduction": deduction, "paid": paid, "remaining": earned - paid})
        total_earned += earned
        total_paid += paid
    return render(request, "attendance_v2/salaries.html", {
        "rows": rows, "year": year, "month": month,
        "total_earned": total_earned, "total_paid": total_paid, "total_remaining": total_earned-total_paid
    })


@login_required
@user_passes_test(has_full_access)
@require_POST
def salary_action(request):
    year, month = _period(request)
    back = _back(year, month)
    employee = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True, is_superuser=False)
    if employee.groups.filter(name__in=["patron", "mudur"]).exists():
        messages.error(request, "Bu hesap personel maaş listesinde bulunmuyor.")
        return redirect(back)
    action = request.POST.get("action")
    try:
        with transaction.atomic():
            if action == "salary":
                amount = _amount(request.POST.get("amount"))
                profile, _ = SalaryProfile.objects.select_for_update().get_or_create(user=employee)
                profile.monthly_net = amount
                profile.save(update_fields=["monthly_net", "updated_at"])
                messages.success(request, "Yeni net maaş tanımlandı. Önceki dönemler değişmedi.")
            elif action in ("adjust", "payment", "lock"):
                period = _get_period(employee, year, month)
                period = SalaryPeriod.objects.select_for_update().get(pk=period.pk)
                if period.locked:
                    raise ValueError("Bu maaş dönemi kesinleştirilmiş, değişiklik yapılamaz.")
                if action == "adjust":
                    period.base_net = _amount(request.POST.get("base_net"))
                    period.adjustment = _amount(request.POST.get("adjustment"))
                    period.deduction = _amount(request.POST.get("deduction"))
                    if period.earned < 0:
                        raise ValueError("Hak ediş sıfırın altında olamaz.")
                    period.save(update_fields=["base_net", "adjustment", "deduction", "updated_at"])
                    messages.success(request, "Dönem maaşı güncellendi.")
                elif action == "payment":
                    amount = _amount(request.POST.get("amount"), positive=True)
                    method = request.POST.get("method")
                    kind = request.POST.get("kind")
                    if method not in dict(SalaryTransaction.METHOD_CHOICES) or kind not in dict(SalaryTransaction.KIND_CHOICES):
                        raise ValueError("Ödeme türü geçersiz.")
                    try:
                        paid_on = date.fromisoformat(request.POST.get("paid_on", ""))
                    except ValueError:
                        raise ValueError("Ödeme tarihi geçersiz.")
                    SalaryTransaction.objects.create(
                        period=period, amount=amount, paid_on=paid_on,
                        method=method, kind=kind, note=(request.POST.get("note") or "")[:300],
                        recorded_by=request.user
                    )
                    messages.success(request, "Ödeme kaydedildi.")
                else:
                    period.locked = True
                    period.save(update_fields=["locked", "updated_at"])
                    messages.success(request, "Maaş dönemi kesinleştirildi.")
            elif action == "void":
                tx = get_object_or_404(SalaryTransaction.objects.select_for_update().select_related("period"),
                    pk=request.POST.get("transaction_id"), period__user=employee, period__year=year, period__month=month)
                if tx.period.locked or tx.voided_at:
                    raise ValueError("Bu ödeme iptal edilemez.")
                tx.voided_at = timezone.now()
                tx.voided_by = request.user
                tx.save(update_fields=["voided_at", "voided_by"])
                messages.success(request, "Ödeme iptal olarak işaretlendi; geçmişi korundu.")
            else:
                raise ValueError("Bilinmeyen işlem.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(back)
