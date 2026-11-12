"""Conservative contact extraction from a business's own public website.

Only explicit tel:, wa.me, WhatsApp and Instagram links are read. Do not
collect free-text personal mobile numbers, private profiles, or scrape Instagram.
Network requests are pinned to validated public IPs (SSRF protection), HTTPS
only, with no redirects, hard byte limits, robots.txt and two-page maximum.
"""
import http.client
import ipaddress
import re
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from django.utils import timezone
from django.db import transaction

from .research import canonical_url
from .models import Prospect

USER_AGENT = "MoliTekstilBusinessResearchBot/1.0"
MAX_PAGE_BYTES = 180_000
MAX_ROBOTS_BYTES = 55_000
CONNECT_TIMEOUT = 4
CONTACT_WORDS = (
    "contact", "kontakt", "contatti", "contacto", "contactez",
    "iletisim", "iletişim", "reach-us", "get-in-touch", "impressum",
)


def business_host(value):
    """Permit ordinary HTTPS business domains, never local networks or IPs."""
    try:
        url = urlsplit((value or "").strip())
        host = (url.hostname or "").lower().rstrip(".")
        if (url.scheme != "https" or not host or url.port not in (None, 443)
                or url.username or url.password or len(host) > 240):
            return ""
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host):
            return ""
        if host.endswith((".local", ".localhost", ".internal", ".test", ".example", ".invalid", ".onion")):
            return ""
        if not canonical_url(value):
            return ""
        if any(host == blocked or host.endswith("." + blocked)
               for blocked in ("instagram.com", "facebook.com", "whatsapp.com",
                               "wa.me", "google.com", "linkedin.com", "tiktok.com")):
            return ""
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:
            return host
    except (ValueError, AttributeError):
        return ""


def public_address(host):
    """Choose an IP only when every DNS response is globally routable."""
    results = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = [row[4][0] for row in results]
    if not ips or not all(ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Public business host resolution failed.")
    return ips[0]


def safe_get(host, ip, path, limit=MAX_PAGE_BYTES):
    """Pinned DNS, TLS certificate validated against host, redirects disabled."""
    if not path.startswith("/") or path.startswith("//") or len(path) > 1600:
        raise ValueError("Invalid public website path")
    conn = http.client.HTTPSConnection(
        host, 443, timeout=CONNECT_TIMEOUT, context=ssl.create_default_context()
    )
    # HTTPSConnection.connect() uses _create_connection. Pin the audited IP
    # instead of re-resolving an attacker-controlled host (DNS rebinding).
    conn._create_connection = (
        lambda address, timeout, source_address=None:
        socket.create_connection((ip, 443), timeout, source_address)
    )
    try:
        conn.request("GET", path, headers={
            "Host": host, "User-Agent": USER_AGENT,
            "Accept": "text/html, text/plain; q=0.5",
            "Accept-Encoding": "identity",
        })
        response = conn.getresponse()
        status = response.status
        media = response.getheader("Content-Type", "").lower()
        if status != 200:
            return status, "", media
        if "text/html" not in media and "text/plain" not in media:
            return status, "", media
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Page too large")
        return status, raw.decode("utf-8", errors="replace"), media
    finally:
        conn.close()


def normalized_number(raw):
    value = unquote(str(raw or "")).strip()
    if not re.fullmatch(r"[+()\d .\-/]{7,35}", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        return ""
    return ("+" if value.startswith("+") else "") + digits


def whatsapp_number(href):
    parsed = urlsplit((href or "").strip())
    host = (parsed.hostname or "").casefold()
    if parsed.scheme == "whatsapp" and parsed.path.strip("/") == "send":
        return normalized_number(parse_qs(parsed.query).get("phone", [""])[0])
    if host in ("wa.me", "www.wa.me"):
        return normalized_number(parsed.path.strip("/").split("/")[0])
    if host in ("api.whatsapp.com", "web.whatsapp.com") and parsed.path.strip("/") == "send":
        return normalized_number(parse_qs(parsed.query).get("phone", [""])[0])
    return ""


class ContactLinks(HTMLParser):
    def __init__(self, base_url, host):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.host = host
        self.phone = ""
        self.whatsapp = ""
        self.instagram = ""
        self.contact_paths = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        href = (attrs.get("href") or "").strip()
        if not href:
            return
        if href.lower().startswith("tel:") and not self.phone:
            self.phone = normalized_number(href[4:].split("?", 1)[0])
            return
        wa = whatsapp_number(href)
        if wa and not self.whatsapp:
            self.whatsapp = wa
            return
        if href.lower().startswith(("http://", "https://", "//")):
            normalized = canonical_url(urljoin(self.base_url, href))
            if normalized.startswith("https://instagram.com/") and not self.instagram:
                self.instagram = normalized
        contact = urlsplit(urljoin(self.base_url, href))
        if (contact.scheme == "https" and contact.hostname == self.host
                and contact.port in (None, 443)
                and any(word in unquote(contact.path).casefold() for word in CONTACT_WORDS)):
            target = contact.path or "/"
            if contact.query:
                target += "?" + contact.query
            if len(target) < 500 and target not in self.contact_paths:
                self.contact_paths.append(target)


def extract_public_business_contacts(website_url):
    """Return found public business channel links with the precise source page."""
    host = business_host(website_url)
    if not host:
        raise ValueError("Tarama için HTTPS kullanan bir işletme web sitesi gerekli.")
    ip = public_address(host)
    base = "https://" + host
    robots_status, robots, _ = safe_get(host, ip, "/robots.txt", MAX_ROBOTS_BYTES)
    if robots_status not in (200, 404):
        raise ValueError("robots.txt erişimi doğrulanamadı; tarama yapılmadı.")
    policy = RobotFileParser()
    policy.set_url(base + "/robots.txt")
    policy.parse(robots.splitlines() if robots_status == 200 else [])
    found = {}
    paths = ["/"]
    for index in range(2):
        if index >= len(paths):
            break
        path = paths[index]
        if not policy.can_fetch(USER_AGENT, base + path):
            continue
        status, html, media = safe_get(host, ip, path)
        if status != 200 or "text/html" not in media:
            continue
        page_url = base + path
        parser = ContactLinks(page_url, host)
        parser.feed(html)
        for key, value in (("phone_number", parser.phone),
                           ("whatsapp_number", parser.whatsapp),
                           ("instagram_url", parser.instagram)):
            if value and not found.get(key):
                found[key] = value
                found[key.replace("_number", "").replace("_url", "") + "_source_url"] = page_url
        if index == 0:
            paths.extend(x for x in parser.contact_paths if x != "/" and x not in paths[:1])
    return found


def enrich_prospect_contact(lead):
    """Fill missing fields only; never overwrite verified/manual values."""
    lead.contact_scan_at = timezone.now()
    if not lead.website_url:
        lead.contact_scan_note = "Web sitesi bulunmadığından taranamadı."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note"])
        return 0
    try:
        contacts = extract_public_business_contacts(lead.website_url)
    except (ValueError, OSError, TimeoutError, ssl.SSLError, http.client.HTTPException) as exc:
        lead.contact_scan_note = "İşletme sitesi güvenli şekilde okunamadı; bilgileri elle kontrol edin."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note"])
        return 0
    updates = []
    for field in ("phone_number", "whatsapp_number", "instagram_url"):
        value = contacts.get(field, "")
        if value and not getattr(lead, field):
            setattr(lead, field, value)
            updates.append(field)
            source_field = {"phone_number": "phone_source_url",
                            "whatsapp_number": "whatsapp_source_url",
                            "instagram_url": "instagram_source_url"}[field]
            setattr(lead, source_field, contacts.get(source_field, "")[:500])
            updates.append(source_field)
    lead.contact_scan_note = (
        ", ".join({"phone_number": "Telefon", "whatsapp_number": "WhatsApp",
                   "instagram_url": "Instagram"}[field]
                  for field in ("phone_number", "whatsapp_number", "instagram_url")
                  if field in updates) + " bulundu."
    ) if updates else "Herkese açık işletme iletişim bağlantısı bulunamadı."
    lead.save(update_fields=["contact_scan_at", "contact_scan_note", *updates])
    return len([x for x in updates if x in ("phone_number", "whatsapp_number", "instagram_url")])



def scan_one_pending_prospect():
    """Slow background enrichment: one unscanned business site per scheduler tick.

    Claims a row before network work so overlapping cron ticks do not crawl
    the same shop repeatedly. Only existing prospect records are considered.
    No personal-number guessing or social-platform scraping.
    """
    with transaction.atomic():
        lead = (Prospect.objects.select_for_update(skip_locked=True)
                .filter(contact_scan_at__isnull=True,
                        website_url__startswith="https://")
                .exclude(status="REJECTED")
                .order_by("created_at", "pk").first())
        if lead is None:
            return {"status": "EMPTY", "found": 0}
        lead.contact_scan_at = timezone.now()
        lead.contact_scan_note = "Otomatik iletişim taraması başlatıldı."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note"])
        lead_id = lead.pk

    lead = Prospect.objects.get(pk=lead_id)
    count = enrich_prospect_contact(lead)
    return {"status": "DONE", "found": count, "prospect_id": lead_id}
