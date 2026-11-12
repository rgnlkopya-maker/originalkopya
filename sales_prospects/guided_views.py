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
    """Search and save up to 20 new candidate results without manual selection."""
    if not _allowed(request):
        return HttpResponseForbidden("Yetkiniz yok.")
    form = GuidedSearchForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Ülke, şehir veya arama kelimesi geçersiz.")
        return redirect("prospect_list")
    if not is_configured():
        messages.warning(
            request,
            "Otomatik Google sonuçları henüz bağlanmadı. "
            "Serper hesabından ücretsiz API anahtarı oluşturulup "
            "Render'a SERPER_API_KEY olarak eklenmeli."
        )
        return redirect("prospect_list")

    query = form.cleaned_data["query"]
    country = form.cleaned_data["country"]
    city = form.cleaned_data["city"]
    search = find_or_start(request.user, country, city, query)
    request.session["active_guided_search_id"] = search.pk
    try:
        result = run_next_page(search, request.user)
    except SearchUnavailable as exc:
        messages.error(request, str(exc))
        return redirect("prospect_list_with_history", history_id=search.pk)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Guided automated search failed")
        messages.error(request, "Arama işlenirken beklenmeyen bir hata oluştu; sayfa ilerlemedi.")
        return redirect("prospect_list_with_history", history_id=search.pk)

    if result["status"] == "EXHAUSTED":
        messages.info(request, "Bu aramanın erişilebilir sonuç sayfaları tamamlandı. Yeni şehir veya arama kelimesi seç.")
    else:
        messages.success(
            request,
            "Google sonuç sayfası {} işlendi: {} sonuç incelendi · {} yeni mağaza · "
            "{} mükerrer · {} uygun olmayan/atlanmış. "
            "İşletmelerin iletişim bağlantıları sırayla araştırılır; mesaj gönderilmedi.".format(
                result["page"], result["seen"], result["new"],
                result["duplicates"], result["skipped"],
            ),
        )
    return redirect("prospect_list_with_history", history_id=search.pk)
