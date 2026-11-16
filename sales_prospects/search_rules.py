"""Literal search queries: no inferred country, language or extra keywords."""
import re

MAX_CURSOR = 60
PROVIDER_PAGE_SIZE = 10
_EXPLICIT_SITE = re.compile(r"(?:^|\s)site:", re.IGNORECASE)


def search_phrase(query, country="", city=""):
    return str(query or "").strip()


def instagram_pass(query, cursor):
    return cursor % 2 == 0 and not _EXPLICIT_SITE.search(search_phrase(query))


def provider_payload(query, country, city, cursor):
    if not 1 <= cursor <= MAX_CURSOR:
        raise ValueError("Search cursor out of range")
    phrase = search_phrase(query)
    if not phrase:
        raise ValueError("Empty search query")
    explicit_site = bool(_EXPLICIT_SITE.search(phrase))
    if instagram_pass(query, cursor):
        phrase = "site:instagram.com " + phrase
    return {"q": phrase, "num": PROVIDER_PAGE_SIZE,
            "page": cursor if explicit_site else (cursor + 1) // 2}


def restricted_query(message):
    return "query pattern not allowed" in str(message).casefold()
