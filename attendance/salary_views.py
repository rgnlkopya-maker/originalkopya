from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from app_settings.access import has_full_access
from .models import SalaryProfile, SalaryPeriod, SalaryTransaction, SalaryRate, SalaryPaymentPlan

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
    # A named month starts on its 6th and ends on the 5th of the following month.
    reference = today if today.day >= 6 else (date(today.year - 1, 12, 6) if today.month == 1 else date(today.year, today.month - 1, 6))
    try:
        year = int(request.GET.get("year") or request.POST.get("year") or reference.year)
        month = int(request.GET.get("month") or request.POST.get("month") or reference.month)
        if not (2020 <= year <= 2100 and 1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        year, month = reference.year, reference.month
    return year, month


def _bounds(year, month):
    start = date(year, month, 6)
    finish = date(year + 1, 1, 5) if month == 12 else date(year, month + 1, 5)
    return start, finish


def _salary_for(user, year, month, fallback):
    _, finish = _bounds(year, month)
    rate = SalaryRate.objects.filter(user=user, start_date__lte=finish).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=finish)
    ).order_by("-start_date").first()
    if rate:
        return rate.monthly_net
    # Never apply a newly entered rate to a historical period lacking a definition.
    if SalaryRate.objects.filter(user=user).exists():
        return ZERO
    return fallback


def _back(year, month):
    return f"{reverse('salary_dashboard')}?year={year}&month={month}"


def _get_period(user, year, month):
    profile, _ = SalaryProfile.objects.get_or_create(user=user)
    period, _ = SalaryPeriod.objects.get_or_create(
        user=user, year=year, month=month, defaults={"base_net": _salary_for(user, year, month, profile.monthly_net)}
    )
    return period


def _team_employees():
    # Same active / not-departed source as Ekipler; hidden salary members remain recoverable.
    employees = User.objects.filter(is_active=True, is_superuser=False).filter(
        Q(hr_profile__employment_end_date__isnull=True) | Q(hr_profile__isnull=True)
    ).exclude(groups__name__iexact="patron").exclude(groups__name__iexact="mudur").distinct()
    return sorted(employees, key=lambda user: (user.get_full_name().strip() or user.username).casefold())


def _salary_employees():
    return [user for user in _team_employees()
            if not hasattr(user, "salary_profile") or user.salary_profile.visible_in_salary]


@login_required
@user_passes_test(has_full_access)
def salary_home(request):
    return render(request, "attendance_v2/salary_home.html")


@login_required
@user_passes_test(has_full_access)
def salary_dashboard(request):
    year, month = _period(request)
    employees = _salary_employees()
    period_start, period_end = _bounds(year, month)
    profiles = {p.user_id: p for p in SalaryProfile.objects.filter(user__in=employees)}
    periods = {p.user_id: p for p in SalaryPeriod.objects.filter(year=year, month=month, user__in=employees).prefetch_related("transactions")}
    plans = list(SalaryPaymentPlan.objects.filter(year=year, month=month, user__in=employees))
    plans_by_user = {}
    for plan in plans:
        plans_by_user.setdefault(plan.user_id, []).append(plan)
    total_planned = sum((p.amount for p in plans if not p.completed), ZERO)
    rows = []
    total_earned = total_paid = ZERO
    for user in employees:
        profile = profiles.get(user.id)
        period = periods.get(user.id)
        base = period.base_net if period else _salary_for(user, year, month, profile.monthly_net if profile else ZERO)
        adjustment = period.adjustment if period else ZERO
        deduction = period.deduction if period else ZERO
        earned = base + adjustment - deduction
        paid = period.total_paid if period else ZERO
        rows.append({"user": user, "profile": profile, "period": period, "base": base, "earned": earned,
                     "adjustment": adjustment, "deduction": deduction, "paid": paid, "remaining": earned - paid,
                     "plans": plans_by_user.get(user.pk, []),
                     "planned": sum((p.amount for p in plans_by_user.get(user.pk, []) if not p.completed), ZERO)})
        total_earned += earned
        total_paid += paid
    return render(request, "attendance_v2/salaries.html", {
        "rows": rows, "year": year, "month": month, "period_start": period_start, "period_end": period_end,
        "total_earned": total_earned, "total_paid": total_paid, "total_remaining": total_earned-total_paid,
        "total_planned": total_planned
    })



@login_required
@user_passes_test(has_full_access)
def salary_definitions(request):
    employees = _salary_employees()
    rates = SalaryRate.objects.filter(user__in=employees).order_by("-start_date", "-id")
    indexed = {}
    for rate in rates:
        indexed.setdefault(rate.user_id, []).append(rate)
    rows = [{"user": employee, "rates": indexed.get(employee.pk, [])} for employee in employees]
    excluded = [user for user in _team_employees() if user not in employees]
    return render(request, "attendance_v2/salary_definitions.html", {"rows": rows, "excluded": excluded})


@login_required
@user_passes_test(has_full_access)
@require_POST
def salary_membership_action(request):
    action = request.POST.get("action")
    if action not in ("hide", "restore"):
        messages.error(request, "Geçersiz personel işlemi.")
        return redirect("salary_definitions")
    person = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True, is_superuser=False)
    if person not in _team_employees():
        messages.error(request, "Bu kişi aktif Ekipler listesinde bulunmuyor.")
        return redirect("salary_definitions")
    profile, _ = SalaryProfile.objects.get_or_create(user=person)
    profile.visible_in_salary = action == "restore"
    profile.save(update_fields=["visible_in_salary", "updated_at"])
    messages.success(request, "Personel maaş listesine eklendi." if action == "restore"
                     else "Personel her iki maaş listesinden çıkarıldı; geçmiş kayıtları korundu.")
    return redirect("salary_definitions")


@login_required
@user_passes_test(has_full_access)
@require_POST
def salary_rate_action(request):
    year, month = _period(request)
    target = reverse('salary_definitions')
    employee = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True, is_superuser=False)
    if employee.groups.filter(name__in=["patron", "mudur"]).exists():
        messages.error(request, "Bu hesap personel listesinde bulunmuyor.")
        return redirect(target)
    try:
        amount = _amount(request.POST.get("amount"))
        start_month = request.POST.get("start_month") or ""
        end_month = request.POST.get("end_month") or ""
        if start_month:
            first = date.fromisoformat(start_month + "-01")
            start = first.replace(day=6)
            if end_month:
                last = date.fromisoformat(end_month + "-01")
                next_month = date(last.year + 1, 1, 5) if last.month == 12 else date(last.year, last.month + 1, 5)
                end = next_month
            else:
                end = None
        else:
            start = date.fromisoformat(request.POST.get("start_date") or "")
            end_raw = request.POST.get("end_date") or ""
            end = date.fromisoformat(end_raw) if end_raw else None
        if end and end < start:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
        with transaction.atomic():
            overlapping = SalaryRate.objects.select_for_update().filter(user=employee).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=start)
            ).filter(Q(start_date__lte=end) if end else Q())
            if overlapping.exists():
                raise ValueError("Bu tarihlerde tanımlı maaş var. Önce dönem çakışmasını giderin.")
            SalaryRate.objects.create(user=employee, monthly_net=amount, start_date=start, end_date=end, created_by=request.user)
            SalaryProfile.objects.update_or_create(user=employee, defaults={"monthly_net": amount})
        messages.success(request, "Maaş ve geçerlilik dönemi kaydedildi. Eski dönem hesapları korunur.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect(target)


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
                linked_plan = SalaryPaymentPlan.objects.select_for_update().filter(payment=tx).first()
                if linked_plan:
                    linked_plan.completed = False
                    linked_plan.payment = None
                    linked_plan.save(update_fields=["completed", "payment"])
                messages.success(request, "Ödeme iptal edildi; varsa ilgili plan yeniden beklemeye alındı.")
            else:
                raise ValueError("Bilinmeyen işlem.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(back)


@login_required
@user_passes_test(has_full_access)
@require_POST
def salary_plan_action(request):
    year, month = _period(request)
    target = _back(year, month)
    employee = get_object_or_404(User, pk=request.POST.get("user_id"), is_active=True, is_superuser=False)
    if employee not in _salary_employees():
        messages.error(request, "Personel maaş listesinde bulunmuyor.")
        return redirect(target)
    action = request.POST.get("action")
    try:
        with transaction.atomic():
            if action == "create":
                amount = _amount(request.POST.get("amount"), positive=True)
                planned_on = date.fromisoformat(request.POST.get("planned_on") or "")
                kind = request.POST.get("kind")
                if kind not in ("advance", "payment"):
                    raise ValueError("Planlanan ödeme türü geçersiz.")
                SalaryPaymentPlan.objects.create(
                    user=employee, year=year, month=month, planned_on=planned_on,
                    amount=amount, kind=kind, note=(request.POST.get("note") or "")[:300],
                    created_by=request.user,
                )
                messages.success(request, "Ödeme planı kaydedildi; maaş bakiyesi değişmedi.")
            elif action in ("pay", "delete"):
                plan = get_object_or_404(
                    SalaryPaymentPlan.objects.select_for_update(),
                    pk=request.POST.get("plan_id"), user=employee, year=year, month=month,
                )
                if action == "pay":
                    if plan.completed or plan.payment_id:
                        raise ValueError("Bu plan için ödeme zaten kaydedilmiş.")
                    method = request.POST.get("method")
                    if method not in dict(SalaryTransaction.METHOD_CHOICES):
                        raise ValueError("Ödeme yöntemi geçersiz.")
                    try:
                        paid_on = date.fromisoformat(request.POST.get("paid_on") or "")
                    except ValueError:
                        raise ValueError("Ödeme tarihi geçersiz.")
                    period = _get_period(employee, year, month)
                    period = SalaryPeriod.objects.select_for_update().get(pk=period.pk)
                    if period.locked:
                        raise ValueError("Kesinleştirilmiş döneme ödeme kaydedilemez.")
                    payment = SalaryTransaction.objects.create(
                        period=period, amount=plan.amount, paid_on=paid_on,
                        method=method, kind=plan.kind, note=plan.note,
                        recorded_by=request.user,
                    )
                    plan.payment = payment
                    plan.completed = True
                    plan.save(update_fields=["completed", "payment"])
                    messages.success(request, "Ödeme kaydedildi; plan tamamlandı ve kalan maaş güncellendi.")
                else:
                    if plan.completed or plan.payment_id:
                        raise ValueError("Ödenmiş plan silinemez. Önce Ödeme Geçmişi'nden ödemeyi iptal edin.")
                    plan.delete()
                    messages.success(request, "Ödeme planı kaldırıldı.")
            else:
                raise ValueError("Geçersiz plan işlemi.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect(target)
