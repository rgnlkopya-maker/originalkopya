"""Extract explicitly published business contacts from public website HTML.

No social account scraping, guesswork, personal contact discovery or external
links are fetched. A phone candidate must be in a tel link, schema.org metadata,
a labelled telephone context, or a standalone phone-like block on a contact
page. Avoid treating arbitrary product codes / addresses as phone numbers.
"""
import json
import re
from html import unescape
from html.parser import HTMLParser

EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", re.I)
PHONE_CANDIDATE = re.compile(
    r"(?<![a-z0-9])(?:\+\s*\d|00\s*\d|0\d)[\d \t()./\-]{6,26}\d(?!\d)",
    re.I,
)
PHONE_LABEL = re.compile(
    r"(?:tel(?:efon|ephone|\.|[- ]?nr\.?)?|phone|mobile|mobil|whatsapp|"
    r"rufnummer|call us|téléphone|telefono|handy|fon|tlf)"
    r"\s*(?:[.:=\-]|\s){0,5}",
    re.I,
)
CONTACT_PATH = re.compile(
    r"(?:kontakt|contact|contatti|contacto|impressum|contact-us|reach-us|"
    r"iletisim|iletişim|informations-legales|mentions-legales)",
    re.I,
)


def clean_phone(value):
    value = unescape(str(value or "")).replace("\xa0", " ")
    value = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    value = value.strip().strip(" :.,;/")
    if not re.fullmatch(r"\+?[\d\s()./\-]{7,36}", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if not 9 <= len(digits) <= 15:
        return ""
    if len(set(digits)) < 3:
        return ""
    return ("+" if value.startswith("+") else "") + digits


def extract_number_from_text(text, is_contact_page=False):
    text = unescape(str(text or "")).replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2212", "-").replace("\xa0", " ")
    # Explicit "Telefon", "Tel.", "Phone" context in normal visible content.
    for match in PHONE_LABEL.finditer(text):
        block = text[match.end():match.end() + 55]
        found = PHONE_CANDIDATE.search(block)
        if found and found.start() < 20:
            number = clean_phone(found.group())
            if number:
                return number
    # Full standalone phone number blocks only on contact/imprint pages.
    if is_contact_page:
        for line in re.split(r"[\r\n]+", text):
            candidate = line.strip(" \t:;,")
            if 9 <= len(candidate) <= 38:
                match = PHONE_CANDIDATE.fullmatch(candidate)
                if match:
                    number = clean_phone(match.group())
                    if number:
                        return number
    return ""


def extract_email_from_text(text):
    text = unescape(str(text or ""))
    for match in re.finditer(
        r"(?<![\w.@])([a-z0-9._%+\-]{1,70}@[a-z0-9.\-]{2,100}\.[a-z]{2,15})(?![\w.@])",
        text, re.I,
    ):
        mail = match.group(1).casefold()
        if EMAIL_RE.fullmatch(mail) and not mail.endswith((".png", ".jpg", ".svg")):
            return mail
    return ""


def schema_contacts(block):
    """Look only for schema.org telephone and email properties."""
    if not block or len(block) > 100_000:
        return {}
    try:
        value = json.loads(block)
    except (ValueError, TypeError):
        return {}
    found = {}
    nodes = [value]
    inspected = 0
    while nodes and inspected < 300:
        node = nodes.pop()
        inspected += 1
        if isinstance(node, list):
            nodes.extend(node[:80])
        elif isinstance(node, dict):
            for key in ("@graph", "contactPoint", "mainEntity", "department", "publisher"):
                child = node.get(key)
                if isinstance(child, (dict, list)):
                    nodes.append(child)
            if not found.get("phone_number") and isinstance(node.get("telephone"), str):
                found["phone_number"] = clean_phone(node["telephone"])
            if not found.get("email") and isinstance(node.get("email"), str):
                value = node["email"].strip().removeprefix("mailto:").casefold()
                if EMAIL_RE.fullmatch(value):
                    found["email"] = value
    return {key: val for key, val in found.items() if val}


class VisibleContacts(HTMLParser):
    def __init__(self, is_contact_page=False):
        super().__init__(convert_charrefs=True)
        self.is_contact_page = is_contact_page
        self.phone_number = ""
        self.email = ""
        self._ignore_depth = 0
        self._ld_json = False
        self._json_buf = []
        self._parts = []
        self._text_length = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        attr = dict(attrs)
        if tag in ("style", "noscript", "svg"):
            self._ignore_depth += 1
        elif tag == "script":
            self._ignore_depth += 1
            self._ld_json = (attr.get("type") or "").casefold() == "application/ld+json"
            self._json_buf = []
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "footer", "section"):
            if self._text_length < 90_000:
                self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag == "script":
            if self._ld_json:
                details = schema_contacts("".join(self._json_buf))
                self.phone_number = self.phone_number or details.get("phone_number", "")
                self.email = self.email or details.get("email", "")
            self._ld_json = False
            self._json_buf = []
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag in ("style", "noscript", "svg"):
            self._ignore_depth = max(0, self._ignore_depth - 1)
        elif tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "footer", "section"):
            if self._text_length < 90_000:
                self._parts.append("\n")

    def handle_data(self, data):
        if self._ld_json:
            if sum(map(len, self._json_buf)) < 100_000:
                self._json_buf.append(data)
        elif self._ignore_depth == 0 and self._text_length < 90_000:
            self._text_length += len(data)
            self._parts.append(data)

    def get_contacts(self):
        plain = " ".join(
            part if part != "\n" else "\n" for part in self._parts
        )
        if not self.phone_number:
            self.phone_number = extract_number_from_text(plain, self.is_contact_page)
        if not self.email:
            self.email = extract_email_from_text(plain)
        return {
            k: v for k, v in (
                ("phone_number", self.phone_number),
                ("email", self.email),
            ) if v
        }
