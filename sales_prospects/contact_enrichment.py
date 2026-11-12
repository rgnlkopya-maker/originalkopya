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
from django.db.models import Q
from datetime import timedelta

from .research import canonical_url
from .models import Prospect
from .published_contacts import VisibleContacts, CONTACT_PATH

USER_AGENT = "MoliTekstilBusinessResearchBot/1.0"
MAX_PAGE_BYTES = 650_000
MAX_ROBOTS_BYTES = 55_000
CONNECT_TIMEOUT = 6
MAX_SITE_PAGES = 4
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
        self.email = ""
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
        if href.lower().startswith("mailto:") and not self.email:
            candidate = unquote(href[7:].split("?", 1)[0]).strip().lower()
            if (len(candidate) <= 254 and
                    re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", candidate)):
                self.email = candidate
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
    """Find public shop contacts on homepage + linked Kontakt/Impressum pages.

    Direct HTTPS and https://www variants are tried separately because many
    sites redirect from bare domain to www. We never follow arbitrary redirects;
    each candidate has its own validated DNS pin, verified TLS and robots rules.
    """
    initial_host = business_host(website_url)
    if not initial_host:
        raise ValueError("Tarama için HTTPS kullanan bir işletme web sitesi gerekli.")
    other = initial_host[4:] if initial_host.startswith("www.") else "www." + initial_host
    variants = [initial_host, other]
    blocked = []

    for host in variants:
        if not business_host("https://" + host):
            continue
        try:
            ip = public_address(host)
            base = "https://" + host
            robots_status, robots, robots_type = safe_get(host, ip, "/robots.txt", MAX_ROBOTS_BYTES)
            if robots_status == 200 and "text/plain" not in robots_type:
                blocked.append("robots.txt doğrulanamadı")
                continue
            if robots_status not in (200, 404):
                blocked.append("robots.txt okunamadı")
                continue
            policy = RobotFileParser()
            policy.set_url(base + "/robots.txt")
            policy.parse(robots.splitlines() if robots_status == 200 else [])
            if not policy.can_fetch(USER_AGENT, base + "/"):
                # A disallow instruction must never be bypassed with www.
                return {}

            found = {}
            seen = set()
            paths = ["/"]
            received_page = False
            while paths and len(seen) < MAX_SITE_PAGES:
                path = paths.pop(0)
                if path in seen or not policy.can_fetch(USER_AGENT, base + path):
                    continue
                seen.add(path)
                try:
                    status, html, media = safe_get(host, ip, path)
                except (ValueError, OSError, TimeoutError, UnicodeError, ssl.SSLError, http.client.HTTPException):
                    # A broken optional page must not erase valid homepage data.
                    continue
                if status != 200 or "text/html" not in media:
                    continue
                received_page = True
                page_url = base + path
                links = ContactLinks(page_url, host)
                links.feed(html)
                visible = VisibleContacts(is_contact_page=bool(CONTACT_PATH.search(path)))
                visible.feed(html)
                text_contacts = visible.get_contacts()

                channels = {
                    "email": links.email or text_contacts.get("email", ""),
                    "phone_number": links.phone or text_contacts.get("phone_number", ""),
                    "whatsapp_number": links.whatsapp,
                    "instagram_url": links.instagram,
                }
                for key, value in channels.items():
                    if value and key not in found:
                        found[key] = value
                        found[{
                            "email": "email_source_url",
                            "phone_number": "phone_source_url",
                            "whatsapp_number": "whatsapp_source_url",
                            "instagram_url": "instagram_source_url",
                        }[key]] = page_url

                if len([c for c in ("phone_number", "email", "whatsapp_number", "instagram_url") if c in found]) == 4:
                    break

                # Follow only clearly labelled on-site contact/imprint links;
                # never crawl product pages or visit external domains.
                if path == "/":
                    ranked = sorted(
                        links.contact_paths,
                        key=lambda p: (
                            0 if CONTACT_PATH.search(p) else 1,
                            0 if "kontakt" in p.lower() or "contact" in p.lower() else 1,
                        ),
                    )
                    for target in ranked[:8]:
                        if target not in seen and target not in paths:
                            paths.append(target)
                    for target in ("/kontakt", "/contact", "/impressum"):
                        if len(paths) >= 8:
                            break
                        if target not in seen and target not in paths:
                            paths.append(target)

            if received_page:
                return found
        except (ValueError, OSError, TimeoutError, UnicodeError, ssl.SSLError, http.client.HTTPException):
            blocked.append("İşletme alan adına erişilemedi")
            continue

    raise ValueError("İşletmenin HTTPS sayfaları veya robots.txt erişilebilir değil.")



def enrich_prospect_contact(lead):
    """Fill missing fields only; never overwrite verified/manual values."""
    lead.contact_scan_at = timezone.now()
    lead.contact_scan_attempts = min(lead.contact_scan_attempts + 1, 65535)
    if not lead.website_url:
        lead.contact_scan_note = "Web sitesi bulunmadığından taranamadı."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note", "contact_scan_attempts"])
        return 0
    try:
        contacts = extract_public_business_contacts(lead.website_url)
    except (ValueError, OSError, TimeoutError, UnicodeError, ssl.SSLError, http.client.HTTPException):
        lead.contact_scan_note = "İşletme sitesi güvenli şekilde okunamadı; bilgileri elle kontrol edin."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note"])
        return 0
    updates = []
    for field in ("email", "phone_number", "whatsapp_number", "instagram_url"):
        value = contacts.get(field, "")
        if value and not getattr(lead, field):
            setattr(lead, field, value)
            updates.append(field)
            source_field = {"email": "email_source_url",
                            "phone_number": "phone_source_url",
                            "whatsapp_number": "whatsapp_source_url",
                            "instagram_url": "instagram_source_url"}[field]
            setattr(lead, source_field, contacts.get(source_field, "")[:500])
            updates.append(source_field)
    lead.contact_scan_note = (
        ", ".join({"email": "E-posta", "phone_number": "Telefon", "whatsapp_number": "WhatsApp",
                   "instagram_url": "Instagram"}[field]
                  for field in ("email", "phone_number", "whatsapp_number", "instagram_url")
                  if field in updates) + " bulundu."
    ) if updates else "Herkese açık işletme iletişim bağlantısı bulunamadı."
    lead.save(update_fields=["contact_scan_at", "contact_scan_note", "contact_scan_attempts", *updates])
    return len([x for x in updates if x in ("email", "phone_number", "whatsapp_number", "instagram_url")])



def scan_one_pending_prospect():
    """Slow background enrichment: one unscanned business site per scheduler tick.

    Claims a row before network work so overlapping cron ticks do not crawl
    the same shop repeatedly. Only existing prospect records are considered.
    No personal-number guessing or social-platform scraping.
    """
    # Retry previously failed scans twice, at most once per six hours.
    # Never retry successful scans, and always prioritize new shop records.
    retry_cutoff = timezone.now() - timedelta(hours=6)
    pending = Q(contact_scan_at__isnull=True) | (
        Q(contact_scan_attempts__lt=3)
        & Q(contact_scan_at__lt=retry_cutoff)
        & (
            Q(contact_scan_note__startswith="İşletme sitesi güvenli şekilde okunamadı")
            | Q(contact_scan_note__startswith="Otomatik iletişim taraması başlatıldı")
        )
    )
    with transaction.atomic():
        lead = (Prospect.objects.select_for_update(skip_locked=True)
                .filter(pending, website_url__startswith="https://")
                .exclude(status="REJECTED")
                .order_by("contact_scan_at", "created_at", "pk").first())
        if lead is None:
            return {"status": "EMPTY", "found": 0}
        lead.contact_scan_at = timezone.now()
        lead.contact_scan_note = "Otomatik iletişim taraması başlatıldı."
        lead.save(update_fields=["contact_scan_at", "contact_scan_note"])
        lead_id = lead.pk

    lead = Prospect.objects.get(pk=lead_id)
    count = enrich_prospect_contact(lead)
    return {"status": "DONE", "found": count, "prospect_id": lead_id}
