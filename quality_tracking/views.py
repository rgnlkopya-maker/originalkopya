from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Order
from .models import QualityIssue

User = get_user_model()


def is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=["patron", "mudur"]).exists()


@login_required
@user_passes_test(is_manager)
def order_quality_issues(request, order_id):
    order = get_object_or_404(Order.objects.select_related("musteri"), pk=order_id)
    issues = order.quality_issues.prefetch_related("sorumlu_personeller").all()
    users = User.objects.filter(is_active=True).exclude(username__in=["patron"]).order_by("username")

    if request.method == "POST":
        konu = (request.POST.get("konu") or "").strip()
        aciklama = (request.POST.get("aciklama") or "").strip()
        asama = (request.POST.get("asama") or "GENEL").strip()
        personel_ids = request.POST.getlist("personeller")

        valid_stages = {value for value, _ in QualityIssue.STAGE_CHOICES}
        if not konu or not aciklama:
            messages.error(request, "Hata konusu ve açıklama zorunludur.")
        elif asama not in valid_stages:
            messages.error(request, "Geçersiz üretim aşaması.")
        else:
            issue = QualityIssue.objects.create(
                order=order,
                konu=konu,
                aciklama=aciklama,
                asama=asama,
                kaydeden=request.user,
            )
            if personel_ids:
                issue.sorumlu_personeller.set(User.objects.filter(id__in=personel_ids, is_active=True))
            messages.success(request, "Hata / müşteri şikayeti kaydedildi. Siparişin son durumu değiştirilmedi.")
            return redirect("quality_tracking:order_issues", order_id=order.id)

    return render(request, "quality_tracking/order_issues.html", {
        "order": order,
        "issues": issues,
        "users": users,
        "stage_choices": QualityIssue.STAGE_CHOICES,
    })


@login_required
@user_passes_test(is_manager)
def resolve_issue(request, issue_id):
    issue = get_object_or_404(QualityIssue, pk=issue_id)
    if request.method == "POST":
        issue.durum = "COZULDU"
        issue.cozum_notu = (request.POST.get("cozum_notu") or "").strip()
        issue.resolved_at = timezone.now()
        issue.save(update_fields=["durum", "cozum_notu", "resolved_at"])
        messages.success(request, "Hata kaydı çözüldü olarak işaretlendi.")
    return redirect("quality_tracking:order_issues", order_id=issue.order_id)


@login_required
@user_passes_test(is_manager)
def reopen_issue(request, issue_id):
    issue = get_object_or_404(QualityIssue, pk=issue_id)
    if request.method == "POST":
        issue.durum = "ACIK"
        issue.resolved_at = None
        issue.save(update_fields=["durum", "resolved_at"])
        messages.success(request, "Hata kaydı tekrar açıldı.")
    return redirect("quality_tracking:order_issues", order_id=issue.order_id)


@login_required
@user_passes_test(is_manager)
def issue_report(request):
    qs = QualityIssue.objects.select_related("order", "order__musteri", "kaydeden").prefetch_related("sorumlu_personeller")

    durum = (request.GET.get("durum") or "").strip()
    personel = (request.GET.get("personel") or "").strip()
    q = (request.GET.get("q") or "").strip()

    if durum in {"ACIK", "COZULDU"}:
        qs = qs.filter(durum=durum)
    if personel:
        qs = qs.filter(sorumlu_personeller__username=personel)
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(konu__icontains=q)
            | Q(aciklama__icontains=q)
            | Q(order__siparis_numarasi__icontains=q)
            | Q(order__urun_kodu__icontains=q)
            | Q(order__musteri__ad__icontains=q)
        )

    qs = qs.distinct()
    users = User.objects.filter(is_active=True).exclude(username="patron").order_by("username")

    return render(request, "quality_tracking/issue_report.html", {
        "issues": qs,
        "users": users,
        "selected_durum": durum,
        "selected_personel": personel,
        "q": q,
    })
