"""Query hints affect search ranking, not the verified address of a store."""
import re
from urllib.parse import urlsplit

COUNTRY_EN = {
    "DE": "Germany", "FR": "France", "GB": "United Kingdom", "US": "United States",
    "NL": "Netherlands", "BE": "Belgium", "AT": "Austria", "CH": "Switzerland",
    "ES": "Spain", "IT": "Italy", "AE": "United Arab Emirates", "SA": "Saudi Arabia",
}
SEARCH_LANG = {
    "DE": "de", "FR": "fr", "GB": "en", "US": "en", "NL": "nl", "BE": "fr",
    "AT": "de", "CH": "de", "ES": "es", "IT": "it", "AE": "en", "SA": "en",
}
LOCATION_HINTS = {
    "berlin": "DE", "hamburg": "DE", "munich": "DE", "frankfurt": "DE",
    "paris": "FR", "lyon": "FR", "marseille": "FR", "london": "GB",
    "manchester": "GB", "amsterdam": "NL", "rotterdam": "NL", "brussels": "BE",
    "vienna": "AT", "wien": "AT", "zurich": "CH", "madrid": "ES",
    "barcelona": "ES", "milan": "IT", "milano": "IT", "rome": "IT",
    "roma": "IT", "dubai": "AE", "riyadh": "SA",
}
SHOP_WORDS = re.compile(r"\b(?:boutique|shop|store|magasin|negozio|tienda|boetiek)\b", re.I)
FASHION_WORDS = re.compile(r"dress|evening|gown|bridal|abiye|robe|abend|braut|formal", re.I)
LISTICLE_TITLE = re.compile(r"^(?:top\s*\d+|\d+\s+best|where\s+(?:can|to)|how\s+to)\b", re.I)
THEME_TITLE = re.compile(r"(?:night in paris|parisian style|themed dresses|is under construction)", re.I)
GENERIC_NAME = re.compile(r"^(?:evening dresses?|dresses?(?: for women)?|women.s evening dresses?.*|wedding and party dresses.*|night in paris dresses?)$", re.I)


def search_phrase(query, country, city=""):
    return " ".join(x for x in ((query or "").strip(), (city or "").strip(),
                                COUNTRY_EN.get(country, "")) if x)


def search_country(query, country="", city=""):
    if country in COUNTRY_EN:
        return country
    words = set(re.findall(r"\w+", (str(query) + " " + str(city)).casefold()))
    matches = {value for place, value in LOCATION_HINTS.items() if place in words}
    return next(iter(matches)) if len(matches) == 1 else ""


def provider_payload(query, country, city, cursor, page_size=10):
    if not 1 <= cursor <= 60:
        raise ValueError("Search cursor out of range")
    phrase = search_phrase(query, country, city)
    if cursor % 2 == 0:
        # The previous 'boutique shop' suffix produced HTTP 400 on the actual
        # account. This shorter query was verified against the same provider.
        phrase = "site:instagram.com " + phrase
    elif FASHION_WORDS.search(phrase) and not SHOP_WORDS.search(phrase):
        phrase += " boutique"
    locale = search_country(query, country, city)
    payload = {"q": phrase, "num": page_size, "page": (cursor + 1) // 2,
               "hl": SEARCH_LANG.get(locale, "en")}
    if locale:
        payload["gl"] = "uk" if locale == "GB" else locale.lower()
    return payload


def clear_nonbusiness_result(title, link):
    title = str(title or "").strip()
    if LISTICLE_TITLE.search(title) or THEME_TITLE.search(title):
        return True
    path = urlsplit(link).path.casefold()
    return any(bit in path for bit in ("/blog/", "/blogs/", "/articles/", "/magazine/"))


def result_name(canonical, cleaned_title):
    """Use the actual domain instead of treating a product category as a name."""
    if GENERIC_NAME.fullmatch(str(cleaned_title or "").strip()):
        return (urlsplit(canonical).hostname or cleaned_title).removeprefix("www.")[:180]
    return cleaned_title


def restricted_query(message):
    return "query pattern not allowed" in str(message).casefold()
