"""Manager-triggered batches of Google web results using Serper's third-party API.

No Google HTML scraping, no Instagram login or DM. Each request processes at
most one provider page and saves the unconsumed results for the next request.
The UI continues requests until 20 NEW prospects or its safety cap is reached.
"""
import json
import logging
import os
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone

from .guided_search import canonical_store_url, clean_title, google_url_for
from .models import GuidedSearch, GuidedSearchHit, Prospect, COUNTRIES
from .research import RETAIL_TERMS, draft_for

LOGGER = logging.getLogger(__name__)
SERPER_ENDPOINT = "https://google.serper.dev/search"
PAGE_SIZE = 20
# Search results are not all potential wholesale buyers. Ignore known
# directories, aggregators and mass-market marketplaces, not boutiques.
NON_RETAILER_HOSTS = {
    "yelp.com", "top10berlin.de", "tripadvisor.com", "trustpilot.com",
    "yellowpages.com", "pagesjaunes.fr", "gelbeseiten.de", "11880.com",
    "zalando.de", "en.zalando.de", "aboutyou.de", "en.aboutyou.de",
    "next.de", "etsy.com", "amazon.de",
}
MAX_PAGES = 30
COUNTRY_EN = {
    "DE": "Germany", "FR": "France", "GB": "United Kingdom",
    "US": "United States", "NL": "Netherlands", "BE": "Belgium",
    "AT": "Austria", "CH": "Switzerland", "ES": "Spain",
    "IT": "Italy", "AE": "United Arab Emirates", "SA": "Saudi Arabia",
}
SEARCH_LANG = {
    "DE": "de", "FR": "fr", "GB": "en", "US": "en", "NL": "nl",
    "BE": "fr", "AT": "de", "CH": "de", "ES": "es",
    "IT": "it", "AE": "en", "SA": "en",
}


class SearchUnavailable(Exception):
    pass


def is_configured():
    return bool(os.environ.get("SERPER_API_KEY", "").strip())


def search_phrase(query, country, city=""):
    return " ".join(x for x in (
        (query or "").strip(), (city or "").strip(),
        COUNTRY_EN.get(country, dict(COUNTRIES).get(country, ""))
    ) if x)


def _fetch_serper_page(api_key, query, country, city, page):
    if not 1 <= page <= MAX_PAGES:
        raise SearchUnavailable("Arama için erişilebilir sonuç sayfası sınırına ulaşıldı.")
    payload = json.dumps({
        "q": search_phrase(query, country, city),
        "num": PAGE_SIZE, "page": page,
        "gl": "uk" if country == "GB" else (country.lower() if country in COUNTRY_EN else "us"),
        "hl": SEARCH_LANG.get(country, "en"),
    }).encode("utf-8")
    request = Request(
        SERPER_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MoliApp/1.0",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            data = json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise SearchUnavailable("Arama servisi kota veya hız sınırına ulaştı.") from exc
        if exc.code in (401, 403):
            raise SearchUnavailable("Arama API anahtarı geçersiz ya da kullanım izni yok.") from exc
        raise SearchUnavailable("Arama servisine ulaşılamadı. Servis ayarlarını kontrol edin.") from exc
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        raise SearchUnavailable("Arama servisine bağlanılamadı; tekrar deneyebilirsiniz.") from exc
    items = data.get("organic", [])
    if not isinstance(items, list):
        raise SearchUnavailable("Arama servisi beklenmeyen bir sonuç biçimi döndürdü.")
    return items[:PAGE_SIZE]


def _store_one(search, item, user):
    if not isinstance(item, dict):
        return "skipped"
    link = str(item.get("link") or "").strip()
    canonical = canonical_store_url(link)
    if not canonical:
        return "skipped"
    from urllib.parse import urlsplit
    host = (urlsplit(canonical).hostname or "").lower()
    if host in NON_RETAILER_HOSTS or any(host.endswith("." + blocked) for blocked in NON_RETAILER_HOSTS):
        return "skipped"
    title = clean_title(item.get("title"), canonical)
    snippet = str(item.get("snippet") or "").strip()[:1000]
    # Use evidence visible in the title/snippet rather than assuming an
    # unrelated site is a store solely because the user searched for shops.
    evidence = (title + " " + snippet).casefold()
    if not any(term in evidence for term in RETAIL_TERMS):
        return "skipped"
    is_instagram = canonical.startswith("https://instagram.com/")
    defaults = {
        "name": title,
        "country": search.country,
        "city": search.city,
        "website_url": "" if is_instagram else ("https://" + canonical.split("://", 1)[1])[:500],
        "instagram_url": canonical if is_instagram else "",
        "instagram_source_url": link[:500] if is_instagram else "",
        "source_url": link[:500],
        "source_snippet": snippet,
        "source": "WEB",
        "status": "NEW",
        "note": "Google sonuç sağlayıcısından bulundu; alıcı ve iletişim uygunluğu doğrulanmadı.",
        "message_draft": draft_for(title, search.country),
        "created_by": user,
    }
    lead, added = Prospect.objects.get_or_create(
        canonical_url=canonical, defaults=defaults,
    )
    if not added:
        # A lead found 6 months ago (or by a different search) still counts
        # as an old lead. Do NOT put it in the new results table.
        return "duplicate"
    GuidedSearchHit.objects.get_or_create(
        search=search, prospect=lead,
        defaults={
            "original_url": link[:500],
            "original_title": title,
            "was_new": True,
        },
    )
    return "new"


def run_next_page(search, user, target_new=PAGE_SIZE):
    """Consume at most one fresh SERP page and return up to target_new NEW shops.

    Never repeat stored candidates, even if the same Google query is recreated
    months later. Unconsumed provider rows stay in pending_results so a click
    that needs 2 fresh shops does not save an extra 18 shops by accident.
    The UI repeats this bounded request to fill a 20-new-lead batch.
    """
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise SearchUnavailable(
            "Google sonuçlarının otomatik aktarımı henüz bağlı değil. "
            "Render'da SERPER_API_KEY tanımlanmalı."
        )
    try:
        target_new = int(target_new)
    except (ValueError, TypeError):
        target_new = PAGE_SIZE
    target_new = min(max(target_new, 1), PAGE_SIZE)
    try:
        return _run_locked_page(search, user, key, target_new)
    except SearchUnavailable as exc:
        GuidedSearch.objects.filter(pk=search.pk).update(last_error=str(exc)[:400])
        raise


def _run_locked_page(search, user, key, target_new):
    """A transaction locks one research cursor; an API call happens at most once."""
    with transaction.atomic():
        locked = GuidedSearch.objects.select_for_update().get(pk=search.pk)
        pending = list(locked.pending_results or [])
        if (locked.exhausted or locked.next_page > MAX_PAGES) and not pending:
            if not locked.exhausted:
                locked.exhausted = True
                locked.save(update_fields=["exhausted"])
            return {
                "status": "EXHAUSTED", "seen": 0, "new": 0,
                "duplicates": 0, "skipped": 0, "page": locked.next_page,
                "pages_fetched": 0, "exhausted": True,
            }
        page_number = locked.next_page
        pages_fetched = 0
        if not pending and page_number <= MAX_PAGES:
            rows = _fetch_serper_page(
                key, locked.query, locked.country, locked.city, page_number
            )
            pages_fetched = 1
            locked.next_page = page_number + 1
            locked.last_page_size = len(rows)
            # Provider objects may contain large snippets. Bound what is
            # retained in the database and never store arbitrary JSON keys.
            pending = [
                {
                    "link": str(item.get("link") or "")[:500],
                    "title": str(item.get("title") or "")[:180],
                    "snippet": str(item.get("snippet") or "")[:1000],
                }
                for item in rows if isinstance(item, dict)
            ]
            if not rows:
                locked.exhausted = True
        counts = {"new": 0, "duplicates": 0, "skipped": 0}
        examined = 0
        while pending and counts["new"] < target_new:
            candidate = pending.pop(0)
            kind = _store_one(locked, candidate, user)
            counts[kind] += 1
            examined += 1

        locked.pending_results = pending
        locked.captured_count += examined
        locked.added_count += counts["new"]
        locked.duplicate_count += counts["duplicates"]
        locked.skipped_count += counts["skipped"]
        locked.last_error = ""
        locked.last_import_at = timezone.now()
        if not pending and locked.next_page > MAX_PAGES:
            locked.exhausted = True
        locked.save(update_fields=[
            "pending_results", "captured_count", "added_count",
            "duplicate_count", "skipped_count", "last_page_size",
            "last_error", "last_import_at", "next_page", "exhausted",
        ])
    return {
        "status": "DONE", "seen": examined, "page": page_number,
        "pages_fetched": pages_fetched,
        "exhausted": locked.exhausted and not locked.pending_results,
        "pending": len(locked.pending_results), **counts,
    }


def find_or_start(user, country, city, query):
    """Identical search terms continue their previous page cursor."""
    query = " ".join(query.split())
    city = " ".join(city.split())
    existing = (
        GuidedSearch.objects.filter(created_by=user, country=country,
                                    city__iexact=city, query__iexact=query,
                                    search_provider="SERPER")
        .order_by("-created_at", "-id").first()
    )
    if existing:
        # A search last used several months ago gets a fresh history session
        # (to capture updated Google rankings), while the global Prospect
        # dedupe keeps all older shops from being counted as new.
        last_used = existing.last_import_at or existing.created_at
        if timezone.now() - last_used < timedelta(days=90):
            return existing
    return GuidedSearch.objects.create(
        created_by=user, country=country, city=city, query=query,
        google_url="https://www.google.com/search?" + urlencode({"q": search_phrase(query, country, city), "num": PAGE_SIZE}),
        search_provider="SERPER",
    )
