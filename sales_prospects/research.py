"""Find publicly indexed business candidates. No Instagram login, scraping or DMs."""
import json
import logging
import os
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import Prospect, SearchRun

logger = logging.getLogger(__name__)
DAILY_LIMIT = 20
START_HOUR = 9
SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Country/retailer-specific, publicly indexed web results; not Instagram scraping.
SEARCHES = [
    ("DE", "Berlin Abendmode Brautmoden Boutique Geschäft Instagram"),
    ("FR", "Paris boutique robe de soirée cérémonie magasin instagram"),
    ("GB", "London eveningwear occasion wear boutique shop instagram"),
    ("NL", "Amsterdam avondjurken bruidsmode boetiek instagram"),
    ("BE", "Brussels evening dress boutique store instagram"),
    ("AT", "Vienna Abendmode Brautmode Boutique instagram"),
    ("CH", "Zurich Abendkleider Brautmode Boutique instagram"),
    ("US", "New York formal evening gowns boutique store instagram"),
    ("ES", "Madrid vestidos de fiesta boutique tienda instagram"),
    ("IT", "Milano abiti da cerimonia boutique negozio instagram"),
    ("AE", "Dubai evening gown boutique formalwear store instagram"),
    ("SA", "Riyadh evening gowns boutique eveningwear store instagram"),
]
SKIP_HOSTS = {
    "amazon.com", "etsy.com", "aliexpress.com", "temu.com", "shein.com",
    "pinterest.com", "facebook.com", "tiktok.com", "youtube.com",
    "linkedin.com", "google.com", "maps.google.com", "tripadvisor.com",
}
SKIP_INSTAGRAM_PATHS = {
    "p", "reel", "reels", "stories", "explore", "accounts",
    "about", "directory", "tags", "locations", "direct",
}
RETAIL_TERMS = (
    "boutique", "bridal", "evening", "gown", "formal", "dress",
    "occasion", "robe", "soirée", "ceremon", "mariage", "boutiq",
    "brautmode", "abendmode", "abendkleid", "avondjurk",
    "fiesta", "abiti", "negozio", "moda", "mağaza", "abiye",
)


def canonical_url(value):
    """Stable business key; one website domain or one Instagram profile."""
    value = (value or "").strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.casefold().removeprefix("www.")
    if host in SKIP_HOSTS or any(host.endswith("." + blocked) for blocked in SKIP_HOSTS):
        return ""
    if host in ("instagram.com", "m.instagram.com"):
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) != 1 or parts[0].lower() in SKIP_INSTAGRAM_PATHS:
            return ""
        return "https://instagram.com/" + parts[0].casefold()
    return "https://" + host


def draft_for(name, country):
    # Curated text, not unverified AI translation or automatic outreach.
    templates = {
        "DE": "Guten Tag,\\nwir sind Moli Tekstil, Hersteller von Abend- und Anlassmode aus der Türkei. Wir beliefern Boutiquen im Großhandel. Dürfen wir Ihnen unsere Kollektion und Großhandelsinformationen senden?\\nMit freundlichen Grüßen, Moli Tekstil",
        "FR": "Bonjour,\\nNous sommes Moli Tekstil, fabricant de robes de soirée et de cérémonie en Turquie. Nous travaillons avec des boutiques en gros. Pouvons-nous vous présenter notre collection et nos conditions professionnelles ?\\nCordialement, Moli Tekstil",
        "ES": "Hola,\\nsomos Moli Tekstil, fabricante de vestidos de fiesta y ceremonia en Turquía. Trabajamos con boutiques al por mayor. ¿Podemos enviarles nuestro catálogo y la información comercial?\\nSaludos, Moli Tekstil",
        "IT": "Buongiorno,\\nsiamo Moli Tekstil, produttori di abiti da sera e da cerimonia in Turchia. Collaboriamo con boutique all'ingrosso. Possiamo inviarvi il catalogo e le informazioni per i rivenditori?\\nCordiali saluti, Moli Tekstil",
        "DEFAULT": "Hello,\\nWe are Moli Tekstil, a manufacturer of evening and occasion dresses in Türkiye. We supply boutiques wholesale. May we share our collection and wholesale information with your store?\\nBest regards, Moli Tekstil",
    }
    return templates.get(country, templates["DEFAULT"]).replace("\\n", "\n")


def _search_web(api_key, query):
    params = urlencode({"q": query, "count": 20, "safesearch": "moderate"})
    request = Request(
        SEARCH_ENDPOINT + "?" + params,
        headers={"Accept": "application/json", "X-Subscription-Token": api_key, "User-Agent": "MoliApp/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=9) as response:
        payload = json.load(response)
    results = payload.get("web", {}).get("results", [])
    if not isinstance(results, list):
        return []
    return results


def _candidate_from_result(item, country):
    if not isinstance(item, dict):
        return None
    url = str(item.get("url") or "")[:500]
    canonical = canonical_url(url)
    if not canonical:
        return None
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("description") or "").strip()
    if not title or not any(term in (title + " " + snippet).casefold() for term in RETAIL_TERMS):
        return None
    title = title.split(" | ")[0].split(" - Instagram")[0].strip()[:180]
    if len(title) < 3:
        return None
    instagram = canonical.startswith("https://instagram.com/")
    return {
        "canonical_url": canonical,
        "name": title,
        "country": country,
        "website_url": "" if instagram else url,
        "instagram_url": url if instagram else "",
        "source_url": url,
        "source_snippet": snippet[:1000],
        "source": "WEB",
        "status": "NEW",
        "message_draft": draft_for(title, country),
    }


def process_daily_search(now=None, manual=False):
    """Persist at most 20 new candidates/day with cross-tick idempotency.

    A Brave API key is required. No key means no fictitious leads and no run.
    """
    now = now or timezone.localtime()
    today = timezone.localtime(now).date()
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        return {"status": "NOT_CONFIGURED", "created": 0}
    if not manual and now.hour < START_HOUR:
        return {"status": "TOO_EARLY", "created": 0}
    with transaction.atomic():
        run, is_new = SearchRun.objects.get_or_create(
            run_date=today, defaults={"status": "RUNNING"}
        )
        if not is_new:
            if not manual or run.status != "ERROR":
                return {"status": run.status, "created": run.created_count}
            run.status = "RUNNING"
            run.error_message = ""
            run.save(update_fields=["status", "error_message"])

    plan_start = today.toordinal() % len(SEARCHES)
    plan = [SEARCHES[(plan_start + n) % len(SEARCHES)] for n in range(4)]
    created = run.created_count
    searched = []
    try:
        for country, query in plan:
            if created >= DAILY_LIMIT:
                break
            searched.append(country)
            for item in _search_web(api_key, query):
                candidate = _candidate_from_result(item, country)
                if not candidate:
                    continue
                key = candidate.pop("canonical_url")
                _, added = Prospect.objects.get_or_create(
                    canonical_url=key, defaults=candidate
                )
                if added:
                    created += 1
                    if created >= DAILY_LIMIT:
                        break
        run.status = "DONE"
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, TypeError) as exc:
        logger.warning("Prospect research failed: %s", type(exc).__name__)
        run.status = "ERROR"
        run.error_message = "Arama sağlayıcısına erişilemedi. Bağlantıyı ve kota durumunu kontrol edin."
    run.created_count = created
    run.searched_countries = ", ".join(searched)
    run.completed_at = timezone.now()
    run.save(update_fields=[
        "status", "created_count", "searched_countries", "error_message", "completed_at"
    ])
    return {"status": run.status, "created": created}
