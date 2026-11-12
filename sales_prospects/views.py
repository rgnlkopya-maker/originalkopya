import os
import csv
import io
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from app_settings.access import has_full_access
from .forms import ProspectForm
from .models import COUNTRIES, Prospect, SearchRun, OutreachEmail
from .research import DAILY_LIMIT, SEARCHES, process_daily_search, canonical_url, draft_for
from .outreach import eligible, queue_initial, queue_followup, config_status, email_from_token, suppress


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
    mailing_enabled, dns_ready, missing_mail_settings = config_status()
    counts = {
        "all": Prospect.objects.count(),
        "mail_queued": OutreachEmail.objects.filter(status="QUEUED").count(),
        "mail_sent": OutreachEmail.objects.filter(status="SENT").count(),
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
        "mailing_enabled": mailing_enabled and dns_ready and not missing_mail_settings,
        "mailing_pending": (not mailing_enabled or not dns_ready or bool(missing_mail_settings)),
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
        sensitive = {"email", "country", "contact_class", "email_basis", "email_source_note", "email_checked", "status", "message_draft"}
        if sensitive.intersection(form.changed_data):
            updated.outreach_approved_at = None
            updated.outreach_approved_by = None
            OutreachEmail.objects.filter(prospect=lead, status="QUEUED").update(
                status="CANCELLED", error_message="İletişim bilgileri değişti; yeni yönetici onayı gerekli."
            )
        if updated.status == "CONTACTED" and previous_status != "CONTACTED":
            updated.last_contacted_at = timezone.now()
        updated.save()
        messages.success(request, "Müşteri kaydı güncellendi; otomatik mesaj gönderilmedi.")
        return redirect("prospect_detail", pk=pk)
    return render(request, "sales_prospects/center.html", {
        "form": form, "form_title": lead.name, "lead": lead,
        "is_new": False, "countries": COUNTRIES,
        "email_approved": eligible(lead)[0],
        "email_issue": eligible(lead)[1],
        "emails": lead.outreach_emails.all()[:10],
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



@login_required
@require_POST
def approve_outreach(request, pk):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    lead = get_object_or_404(Prospect, pk=pk)
    allowed, reason = eligible(lead, require_approval=False)
    if not allowed:
        messages.error(request, reason)
        return redirect("prospect_detail", pk=pk)
    lead.outreach_approved_at = timezone.now()
    lead.outreach_approved_by = request.user
    if lead.status in ("NEW", "REVIEWED"):
        lead.status = "APPROVED"
    lead.save(update_fields=["outreach_approved_at", "outreach_approved_by", "status", "updated_at"])
    mail, why = queue_initial(lead, request.user)
    if mail and not why:
        messages.success(request, "İlk tanıtım taslağı kuyruğa alındı. Gönderim servisi etkin değilse e-posta gönderilmez.")
    elif mail:
        messages.info(request, why)
    else:
        messages.warning(request, why or "Kuyruk oluşturulamadı.")
    return redirect("prospect_detail", pk=pk)


@login_required
@require_POST
def queue_outreach_followup(request, pk):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    lead = get_object_or_404(Prospect, pk=pk)
    mail, reason = queue_followup(lead, request.user)
    if mail and not reason:
        messages.success(request, "Bir adet takip e-postası kuyruğa alındı.")
    else:
        messages.warning(request, reason)
    return redirect("prospect_detail", pk=pk)


@login_required
@require_POST
def stop_outreach(request, pk):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    lead = get_object_or_404(Prospect, pk=pk)
    if lead.email:
        suppress(lead.email, "MANUAL")
    messages.success(request, "Bu adres tüm ihracat satış gönderimlerinden çıkarıldı.")
    return redirect("prospect_detail", pk=pk)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe_public(request, token):
    """Signed one-click POST (RFC 8058) and human-readable confirmation page."""
    address = email_from_token(token)
    if not address:
        return HttpResponse("Invalid or expired unsubscribe link.", status=400, content_type="text/plain")
    if request.method == "POST":
        suppress(address)
        return HttpResponse("You have been unsubscribed from Moli Tekstil sales emails.", content_type="text/plain")
    from django.utils.html import escape
    # A GET from a security scanner never unsubscribes a recipient.
    return HttpResponse(
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>Unsubscribe</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<main style='max-width:480px;margin:60px auto;font:16px Arial,sans-serif'>"
        "<h1>Moli Tekstil</h1><p>Stop receiving commercial emails at "
        + escape(address) + "?</p><form method='post'><button type='submit' "
        "style='background:#463e92;border:0;border-radius:8px;color:#fff;padding:12px 18px'>"
        "Unsubscribe</button></form></main></html>",
        content_type="text/html",
    )



@login_required
@require_POST
def import_prospect_csv(request):
    """Import opted-in or publicly sourced B2B leads for review, never auto-approve."""
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    upload = request.FILES.get("file")
    if not upload or upload.size > 2 * 1024 * 1024:
        messages.error(request, "UTF-8 CSV dosyası seçin (en fazla 2 MB).")
        return redirect("prospect_list")
    try:
        content = upload.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or not {"name", "country"}.issubset(set(reader.fieldnames)):
            raise ValueError("CSV'de name ve country sütunları bulunmalı.")
    except (UnicodeError, csv.Error, ValueError):
        messages.error(request, "CSV okunamadı: UTF-8 formatı ve name/country başlıklarını kontrol edin.")
        return redirect("prospect_list")

    added = 0
    skipped = 0
    for i, row in enumerate(reader):
        if i >= 2000:
            skipped += 1
            break
        name = (row.get("name") or "").strip()[:180]
        country = (row.get("country") or "").strip().upper()
        country = {"UK": "GB", "USA": "US"}.get(country, country)
        website = (row.get("website") or "").strip()[:500]
        instagram = (row.get("instagram") or "").strip()[:500]
        raw_email = (row.get("email") or "").strip().casefold()[:254]
        key = canonical_url(instagram or website)
        if not name or country not in dict(COUNTRIES) or not key:
            skipped += 1
            continue
        if raw_email:
            try:
                validate_email(raw_email)
            except ValidationError:
                raw_email = ""
        _, created = Prospect.objects.get_or_create(
            canonical_url=key,
            defaults={
                "name": name, "country": country,
                "city": (row.get("city") or "").strip()[:100],
                "website_url": website if canonical_url(website) else "",
                "instagram_url": instagram if canonical_url(instagram).startswith("https://instagram.com/") else "",
                "source_url": (row.get("source_url") or "").strip()[:500],
                "email": raw_email, "message_draft": draft_for(name, country),
                "created_by": request.user,
                "source": "MANUAL", "status": "NEW",
                "note": "CSV ile eklendi; iletişim dayanağı ve e-posta kontrolü yapılmadı.",
            },
        )
        if created:
            added += 1
        else:
            skipped += 1
    messages.success(request, f"CSV aktarıldı: {added} yeni aday, {skipped} atlanan / mükerrer kayıt. Hiçbir e-posta gönderilmedi.")
    return redirect("prospect_list")


@login_required
@require_GET
def prospect_csv_template(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="moli-yurtdisi-musteriler-ornek.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["name", "country", "city", "website", "instagram", "email", "source_url"])
    writer.writerow(["Example Eveningwear Boutique", "US", "New York", "https://example.com", "", "", "https://example.com"])
    return response
