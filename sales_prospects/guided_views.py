"""Manager-initiated Google research sessions. Google search itself opens in a tab."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from app_settings.access import has_full_access
from .forms import GuidedSearchForm
from .guided_search import google_url_for, import_selected_results
from .models import GuidedSearch
from .automatic_search import find_or_start, run_next_page, SearchUnavailable, is_configured


def _allowed(request):
    return has_full_access(request.user)


@login_required
@require_POST
def start(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    form = GuidedSearchForm(request.POST)
    if not form.is_valid():
        detail = "Ülke, şehir ve arama kelimelerini kontrol edin."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": detail}, status=400)
        messages.error(request, detail)
        return redirect("prospect_list")

    country = form.cleaned_data["country"]
    city = form.cleaned_data["city"]
    query = form.cleaned_data["query"]
    search = GuidedSearch.objects.create(
        created_by=request.user,
        country=country,
        city=city,
        query=query,
        google_url=google_url_for(query, country, city),
    )
    request.session["active_guided_search_id"] = search.pk
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True, "id": search.pk,
            "google_url": search.google_url,
        })
    messages.success(request, "Arama geçmişe kaydedildi. Google'ı açıp mağazaları seçebilirsiniz.")
    return redirect("prospect_list")


@login_required
@require_POST
def import_results(request):
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    try:
        search_id = int(request.POST.get("search_id") or request.session.get("active_guided_search_id") or 0)
    except (TypeError, ValueError):
        search_id = 0
    search = GuidedSearch.objects.filter(pk=search_id, created_by=request.user).first()
    if not search:
        messages.error(request, "Aktarım için önce arama başlatmalısınız.")
        return redirect("prospect_list")
    raw = request.POST.get("results_json") or request.POST.get("result_urls") or ""
    if not raw.strip():
        messages.error(request, "Aktarılacak mağaza bağlantısı bulunamadı.")
        return redirect("prospect_list")
    try:
        summary = import_selected_results(search, raw, request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("prospect_list")
    request.session["active_guided_search_id"] = search.pk
    messages.success(
        request,
        "{} yeni mağaza eklendi · {} zaten kayıtlı · {} atlandı. "
        "İletişim bilgileri kayıtlı mağaza web sitelerinden sırayla araştırılacak; mesaj gönderilmedi.".format(
            summary["new"], summary["duplicates"], summary["skipped"],
        ),
    )
    return redirect("prospect_list_with_history", history_id=search.pk)



@login_required
@require_POST
def automatic_next_batch(request):
    """Serve one bounded results page, optionally as an AJAX fill-to-20 step."""
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    form = GuidedSearchForm(request.POST)
    if not form.is_valid():
        issue = "Ülke, şehir veya arama kelimesi geçersiz."
        if ajax:
            return JsonResponse({"ok": False, "error": issue}, status=400)
        messages.error(request, issue)
        return redirect("prospect_list")
    if not is_configured():
        issue = (
            "Serper bağlantısı bulunamadı. Render ortamında SERPER_API_KEY "
            "tanımlanmalı."
        )
        if ajax:
            return JsonResponse({"ok": False, "error": issue}, status=503)
        messages.warning(request, issue)
        return redirect("prospect_list")

    query = form.cleaned_data["query"]
    country = form.cleaned_data["country"]
    city = form.cleaned_data["city"]
    search = find_or_start(request.user, country, city, query)
    request.session["active_guided_search_id"] = search.pk
    try:
        result = run_next_page(
            search, request.user, target_new=request.POST.get("target_new", "20")
        )
    except SearchUnavailable as exc:
        if ajax:
            return JsonResponse(
                {"ok": False, "error": str(exc), "search_id": search.pk},
                status=503,
            )
        messages.error(request, str(exc))
        return redirect("prospect_list_with_history", history_id=search.pk)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Guided automated search failed")
        issue = "Arama işlenirken hata oluştu; mevcut kayıtlar korunuyor."
        if ajax:
            return JsonResponse({"ok": False, "error": issue, "search_id": search.pk}, status=500)
        messages.error(request, issue)
        return redirect("prospect_list_with_history", history_id=search.pk)

    if ajax:
        return JsonResponse({"ok": True, "search_id": search.pk, **result})

    if result["status"] == "EXHAUSTED":
        messages.info(
            request,
            "Bu araştırmada erişilebilir sonuçlar tamamlandı. "
            "Başka şehir veya arama kelimesi deneyin.",
        )
    else:
        messages.success(
            request,
            "{} yeni mağaza bulundu, {} eski mağaza atlandı, "
            "{} uygun olmayan sonuç elendi. Daha fazla yeni mağaza için "
            "tekrar arayabilirsin.".format(
                result["new"], result["duplicates"], result["skipped"]
            ),
        )
    return redirect("prospect_list_with_history", history_id=search.pk)
