import os
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from app_settings.access import has_full_access
from .forms import ProspectForm
from .models import COUNTRIES, Prospect, SearchRun
from .research import DAILY_LIMIT, SEARCHES, process_daily_search


def _allowed(request):
    return has_full_access(request.user)


@login_required
@require_GET
def prospect_list(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yurt Dışı Müşteri Merkezi yalnız patron ve müdür içindir.")
    base = Prospect.objects.all()
    status = request.GET.get("status", "")
    country = request.GET.get("country", "")
    term = request.GET.get("q", "").strip()[:80]
    if status in dict(Prospect.STATUS):
        base = base.filter(status=status)
    else:
        status = ""
    if country in dict(COUNTRIES):
        base = base.filter(country=country)
    else:
        country = ""
    if term:
        from django.db.models import Q
        base = base.filter(Q(name__icontains=term) | Q(city__icontains=term))
    page = Paginator(base, 25).get_page(request.GET.get("page"))
    today_run = SearchRun.objects.filter(run_date=timezone.localdate()).first()
    counts = {
        "all": Prospect.objects.count(),
        "new": Prospect.objects.filter(status="NEW").count(),
        "contacted": Prospect.objects.filter(status="CONTACTED").count(),
        "responded": Prospect.objects.filter(status__in=("REPLIED", "QUALIFIED", "CUSTOMER")).count(),
    }
    search_links = [
        {"country": label, "url": "https://www.google.com/search?q=" + quote_plus(query)}
        for code, query in SEARCHES[:5]
        for key, label in COUNTRIES if code == key
    ]
    return render(request, "sales_prospects/center.html", {
        "page": page, "counts": counts, "countries": COUNTRIES,
        "statuses": Prospect.STATUS, "selected_status": status,
        "selected_country": country, "term": term, "today_run": today_run,
        "api_configured": bool(os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()),
        "daily_limit": DAILY_LIMIT, "search_links": search_links,
    })


@login_required
@require_http_methods(["GET", "POST"])
def prospect_new(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    form = ProspectForm(request.POST or None, initial={"status": "NEW"})
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.created_by = request.user
        lead.save()
        messages.success(request, "Müşteri adayı eklendi. Herhangi bir mesaj gönderilmedi.")
        return redirect("prospect_detail", pk=lead.pk)
    return render(request, "sales_prospects/center.html", {
        "form": form, "form_title": "Yeni müşteri adayı",
        "is_new": True, "countries": COUNTRIES,
    })


@login_required
@require_http_methods(["GET", "POST"])
def prospect_detail(request, pk):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    lead = get_object_or_404(Prospect, pk=pk)
    previous_status = lead.status
    form = ProspectForm(request.POST or None, instance=lead)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if updated.status == "CONTACTED" and previous_status != "CONTACTED":
            updated.last_contacted_at = timezone.now()
        updated.save()
        messages.success(request, "Müşteri kaydı güncellendi; otomatik mesaj gönderilmedi.")
        return redirect("prospect_detail", pk=pk)
    return render(request, "sales_prospects/center.html", {
        "form": form, "form_title": lead.name, "lead": lead,
        "is_new": False, "countries": COUNTRIES,
    })


@login_required
@require_POST
def search_today(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    result = process_daily_search(manual=True)
    status = result["status"]
    if status == "NOT_CONFIGURED":
        messages.warning(request, "Otomatik mağaza araştırması için Render ortamında BRAVE_SEARCH_API_KEY tanımlanmalı. Anahtar olmadan gerçek aday üretilmez.")
    elif status == "ERROR":
        messages.error(request, "Arama servisinde hata oldu. Önce bağlantıyı veya kotayı kontrol edin.")
    elif status == "RUNNING":
        messages.info(request, "Bugünkü araştırma zaten çalışıyor.")
    else:
        messages.success(request, f"Bugünkü araştırma: {result['created']} yeni aday kaydı. Tekrarlanan mağazalar atlandı. Mesaj gönderilmedi.")
    return redirect("prospect_list")
