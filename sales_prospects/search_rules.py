"""Literal search queries, with no inferred location or shopping-keyword suffix."""
import re

MAX_CURSOR = 60
PROVIDER_PAGE_SIZE = 10
_EXPLICIT_SITE = re.compile(r"(?:^|\s)site:", re.IGNORECASE)


def search_phrase(query, country="", city=""):
    """Legacy arguments stay accepted, but never change the user's query."""
    return str(query or "").strip()


def provider_payload(query, country, city, cursor):
    if not 1 <= cursor <= MAX_CURSOR:
        raise ValueError("Search cursor out of range")
    phrase = search_phrase(query)
    if not phrase:
        raise ValueError("Empty search query")
    # An additional, explicitly Instagram-focused pass uses only the site
    # operator. The normal web query is sent exactly as entered.
    if cursor % 2 == 0 and not _EXPLICIT_SITE.search(phrase):
        phrase = "site:instagram.com " + phrase
    return {"q": phrase, "num": PROVIDER_PAGE_SIZE, "page": (cursor + 1) // 2}


def restricted_query(message):
    return "query pattern not allowed" in str(message).casefold()
