"""User-directed web search recording and selected-result import.

No automated Google requests or scraping on the server. The user controls
searches and explicitly selects links, which enter the CRM as UNVERIFIED leads.
"""
import ipaddress
import json
import re
from urllib.parse import urlencode, urlsplit

from django.db import transaction
from django.utils import timezone

from .models import COUNTRIES, GuidedSearch, GuidedSearchHit, Prospect
from .research import canonical_url, draft_for

MAX_RESULTS_PER_IMPORT = 50
MAX_IMPORT_JSON_BYTES = 35_000
GOOGLE_URL = "https://www.google.com/search"
EXCLUDED_DOMAINS = {
    "google.com", "google.co.uk", "google.de", "google.fr", "google.com.tr",
    "youtube.com", "youtu.be", "pinterest.com", "facebook.com", "tiktok.com",
    "twitter.com", "x.com", "linkedin.com", "reddit.com", "amazon.com",
    "etsy.com", "tripadvisor.com", "maps.google.com",
}


def google_url_for(query, country, city=""):
    names = dict(COUNTRIES)
    country_name = names.get(country, "")
    composed = " ".join(bit for bit in [query.strip(), city.strip(), country_name] if bit)
    return GOOGLE_URL + "?" + urlencode({"q": composed, "num": 20})


def canonical_store_url(url):
    """Only public, ordinary HTTPS shop websites or Instagram profiles."""
    value = (url or "").strip()
    if len(value) > 500:
        return ""
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in ("https", "http") or not host:
            return ""
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return ""
        if host in EXCLUDED_DOMAINS or any(
            host.endswith("." + d) for d in EXCLUDED_DOMAINS
        ):
            return ""
        if (host.endswith((".local", ".internal", ".localhost", ".invalid", ".onion"))
                or host == "localhost"):
            return ""
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:
            pass
        result = canonical_url(value)
        if not result:
            return ""
        # Reject directory and search results pages instead of incorrectly
        # treating their own domain as a bridal store.
        if host in ("bing.com", "duckduckgo.com", "search.yahoo.com"):
            return ""
        return result
    except (ValueError, AttributeError):
        return ""


def clean_title(title, canonical):
    raw = re.sub(r"\s+", " ", str(title or "")).strip()
    for separator in (" | ", " – ", " — "):
        if separator in raw:
            raw = raw.split(separator)[0]
    if raw.lower().endswith(" - instagram"):
        raw = raw[:-12]
    if len(raw) < 3:
        host = urlsplit(canonical).hostname or ""
        raw = host.split(".")[0].replace("-", " ").title()
    return raw[:180]


def normalized_results(raw):
    """Accept browser helper JSON or one URL / title|URL per pasted line."""
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_IMPORT_JSON_BYTES:
            raise ValueError("Çok fazla bağlantı gönderildi. En fazla 50 sonuç seçin.")
        try:
            items = json.loads(raw)
        except (ValueError, TypeError):
            items = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    name, url = line.split("|", 1)
                elif "\t" in line:
                    name, url = line.split("\t", 1)
                else:
                    name, url = "", line
                items.append({"name": name.strip(), "url": url.strip()})
    else:
        items = raw
    if not isinstance(items, list):
        raise ValueError("Arama sonuçları beklenen biçimde değil.")
    if len(items) > MAX_RESULTS_PER_IMPORT:
        raise ValueError("Bir işlemde en fazla 50 mağaza bağlantısı aktarılabilir.")
    return items


@transaction.atomic
def import_selected_results(search, raw, creator):
    items = normalized_results(raw)
    new = duplicates = skipped = 0
    seen = set()

    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        raw_url = str(item.get("url") or "").strip()[:501]
        canonical = canonical_store_url(raw_url)
        if not canonical:
            skipped += 1
            continue
        if canonical in seen:
            skipped += 1
            continue
        seen.add(canonical)
        title = clean_title(item.get("name"), canonical)
        is_instagram = canonical.startswith("https://instagram.com/")
        defaults = {
            "name": title,
            "country": search.country,
            "city": search.city,
            "website_url": "" if is_instagram else raw_url,
            "instagram_url": canonical if is_instagram else "",
            "instagram_source_url": raw_url if is_instagram else "",
            "source_url": raw_url,
            "source": "MANUAL",
            "source_snippet": "Kullanıcı tarafından Google sonuçlarından seçilen bağlantı.",
            "status": "NEW",
            "note": "Google aramasından seçildi. Mağaza ve iletişim bilgileri henüz doğrulanmadı.",
            "message_draft": draft_for(title, search.country),
            "created_by": creator,
        }
        lead, created = Prospect.objects.get_or_create(canonical_url=canonical, defaults=defaults)
        hit, hit_added = GuidedSearchHit.objects.get_or_create(
            search=search, prospect=lead,
            defaults={
                "original_url": raw_url,
                "original_title": title,
                "was_new": created,
            },
        )
        if created:
            new += 1
        else:
            duplicates += 1
        if not hit_added:
            # Re-importing the same selected result must not inflate the
            # historical count or create duplicate search result rows.
            skipped += 1

    search.captured_count += len(items)
    search.added_count += new
    search.duplicate_count += duplicates
    search.skipped_count += skipped
    search.last_import_at = timezone.now()
    search.save(update_fields=[
        "captured_count", "added_count", "duplicate_count",
        "skipped_count", "last_import_at",
    ])
    return {"new": new, "duplicates": duplicates, "skipped": skipped, "selected": len(items)}
