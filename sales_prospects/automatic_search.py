"""Manager-triggered batches of Google web results using Serper's third-party API.

No Google HTML scraping, no Instagram login or DM. Each request consumes one
search-results page (up to 20 organic results). Search history keeps the next
page cursor. Only discovered public business websites are later enriched.
"""
import json
import logging
import os
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
    _, hit_added = GuidedSearchHit.objects.get_or_create(
        search=search, prospect=lead,
        defaults={
            "original_url": link[:500],
            "original_title": title,
            "was_new": added,
        },
    )
    if not hit_added:
        return "skipped"
    return "new" if added else "duplicate"


def run_next_page(search, user):
    """Fetch the NEXT page exactly once, and persist counts under a row lock.

    Concurrent requests for one session serialize. If provider fails, page
    number doesn't advance; the manager can retry without losing position.
    """
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise SearchUnavailable(
            "Google sonuçlarının otomatik aktarımı henüz bağlı değil. "
            "Render'da SERPER_API_KEY tanımlanmalı."
        )
    try:
        return _run_locked_page(search, user, key)
    except SearchUnavailable as exc:
        GuidedSearch.objects.filter(pk=search.pk).update(last_error=str(exc)[:400])
        raise


def _run_locked_page(search, user, key):
    with transaction.atomic():
        locked = GuidedSearch.objects.select_for_update().get(pk=search.pk)
        if locked.exhausted or locked.next_page > MAX_PAGES:
            return {"status": "EXHAUSTED", "seen": 0, "new": 0, "duplicates": 0, "skipped": 0, "page": locked.next_page}
        page_number = locked.next_page
        rows = _fetch_serper_page(
            key, locked.query, locked.country, locked.city, page_number
        )
        counts = {"new": 0, "duplicates": 0, "skipped": 0}
        for row in rows:
            kind = _store_one(locked, row, user)
            counts[kind] += 1
        locked.captured_count += len(rows)
        locked.added_count += counts["new"]
        locked.duplicate_count += counts["duplicates"]
        locked.skipped_count += counts["skipped"]
        locked.last_page_size = len(rows)
        locked.last_error = ""
        locked.last_import_at = timezone.now()
        locked.next_page = page_number + 1
        locked.exhausted = (len(rows) < PAGE_SIZE or locked.next_page > MAX_PAGES)
        locked.save(update_fields=[
            "captured_count", "added_count", "duplicate_count",
            "skipped_count", "last_page_size", "last_error", "last_import_at",
            "next_page", "exhausted",
        ])
    return {
        "status": "DONE",
        "seen": len(rows), "page": page_number,
        "exhausted": locked.exhausted, **counts,
    }


def find_or_start(user, country, city, query):
    """Identical search terms continue their previous page cursor."""
    query = query.strip()
    city = city.strip()
    existing = (
        GuidedSearch.objects.filter(created_by=user, country=country,
                                    city__iexact=city, query__iexact=query,
                                    search_provider="SERPER")
        .order_by("-created_at", "-id").first()
    )
    if existing:
        return existing
    return GuidedSearch.objects.create(
        created_by=user, country=country, city=city, query=query,
        google_url="https://www.google.com/search?" + urlencode({"q": search_phrase(query, country, city), "num": PAGE_SIZE}),
        search_provider="SERPER",
    )
