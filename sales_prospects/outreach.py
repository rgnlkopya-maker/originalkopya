"""Permission-reviewed export sales email workflow.

Email sending is OFF unless explicitly enabled and fully configured on Render.
No Instagram/WhatsApp automation and no automatic harvesting of email addresses.
"""
import logging
import os
from datetime import timedelta
from urllib.parse import quote

from django.core import signing
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone

from .models import OutreachEmail, Prospect, SuppressedEmail

logger = logging.getLogger(__name__)
SALT = "moli-export-sales-opt-out-v1"
MAX_DAILY_EMAILS = 25


def normalized_email(value):
    return (value or "").strip().casefold()


def eligible(lead, *, require_approval=True):
    """Fail closed until a manager has reviewed the actual company/contact."""
    email = normalized_email(lead.email)
    if not email or "@" not in email:
        return False, "Kurumsal e-posta adresi girilmedi."
    if lead.status in ("REJECTED", "CUSTOMER", "REPLIED"):
        return False, "Mağazanın görüşme durumu otomatik tanıtıma uygun değil."
    if not lead.email_checked or not (lead.email_source_note or "").strip():
        return False, "Adres doğrulama ve iletişim dayanağı açıklaması eksik."
    if lead.email_basis == "CONSENT":
        pass
    elif lead.country == "US" and lead.email_basis == "US_B2B" and lead.contact_class == "COMPANY":
        pass
    elif lead.country == "GB" and lead.email_basis == "GB_CORP" and lead.contact_class == "COMPANY":
        pass
    else:
        return False, "Ülkeye ve şirket türüne uygun iletişim izni/dayanağı doğrulanmamış."
    if require_approval and not lead.outreach_approved_at:
        return False, "Yönetici e-posta onayı bekleniyor."
    if SuppressedEmail.objects.filter(email=email).exists():
        return False, "Adres iletişimden çıkma/engelleme listesinde."
    return True, ""


def subject_for(country):
    return {
        "DE": "Abendmode für Ihr Geschäft | Moli Tekstil",
        "FR": "Collection de robes de soirée pour votre boutique | Moli Tekstil",
        "ES": "Vestidos de fiesta al por mayor | Moli Tekstil",
        "IT": "Abiti da cerimonia per la vostra boutique | Moli Tekstil",
    }.get(country, "Wholesale eveningwear collection | Moli Tekstil")


def queue_initial(lead, manager):
    allowed, reason = eligible(lead)
    if not allowed:
        return None, reason
    if lead.status == "CONTACTED" or lead.last_contacted_at:
        return None, "Daha önce iletişim kurulan mağazaya yeni ilk tanıtım gönderilemez."
    email = normalized_email(lead.email)
    if OutreachEmail.objects.filter(
        email__iexact=email, kind="INITIAL", status__in=("QUEUED", "SENDING", "SENT")
    ).exclude(prospect=lead).exists():
        return None, "Bu e-posta adresi başka bir mağaza kaydında zaten kullanılmış."
    item, created = OutreachEmail.objects.get_or_create(
        prospect=lead, kind="INITIAL",
        defaults={
            "email": normalized_email(lead.email),
            "subject": subject_for(lead.country),
            "body": lead.message_draft,
            "scheduled_at": timezone.now(),
            "approved_by": manager,
        },
    )
    return item, "" if created else "Bu mağaza için ilk tanıtım zaten kaydedilmiş."


def queue_followup(lead, manager):
    allowed, reason = eligible(lead)
    if not allowed:
        return None, reason
    initial = OutreachEmail.objects.filter(prospect=lead, kind="INITIAL", status="SENT").first()
    if not initial or not initial.sent_at or initial.sent_at > timezone.now() - timedelta(days=7):
        return None, "İlk e-posta gönderildikten en az 7 gün geçmeli."
    if lead.status in ("REPLIED", "QUALIFIED", "CUSTOMER", "REJECTED"):
        return None, "Yanıt veren veya kapanan mağazaya otomatik takip gönderilmez."
    followup_body = (
        "Hello,\n\nWe wanted to follow up on our wholesale eveningwear collection. "
        "If you would like to see our catalogue, please reply to this email.\n\n"
        "Best regards,\nMoli Tekstil"
    )
    item, created = OutreachEmail.objects.get_or_create(
        prospect=lead, kind="FOLLOWUP",
        defaults={
            "email": normalized_email(lead.email),
            "subject": "Follow-up: Moli Tekstil wholesale collection",
            "body": followup_body,
            "scheduled_at": timezone.now(),
            "approved_by": manager,
        },
    )
    return item, "" if created else "Takip e-postası daha önce kaydedilmiş."


def config_status():
    required = (
        "MOLI_OUTREACH_FROM", "MOLI_OUTREACH_SMTP_HOST",
        "MOLI_OUTREACH_SMTP_USER", "MOLI_OUTREACH_SMTP_PASSWORD",
        "MOLI_OUTREACH_POSTAL_ADDRESS", "MOLI_OUTREACH_PUBLIC_URL",
        "MOLI_OUTREACH_PRIVACY_URL",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    enabled = os.environ.get("MOLI_OUTREACH_ENABLED", "").strip().lower() in ("1", "true", "yes")
    domain_verified = os.environ.get("MOLI_OUTREACH_DNS_VERIFIED", "").strip().lower() in ("1", "true", "yes")
    return enabled, domain_verified, missing


def unsubscribe_token(email):
    return signing.dumps({"email": normalized_email(email)}, salt=SALT, compress=True)


def email_from_token(token):
    try:
        data = signing.loads(token, salt=SALT, max_age=5 * 365 * 86400)
    except signing.BadSignature:
        return ""
    return normalized_email(data.get("email", ""))


def suppress(email, reason="UNSUBSCRIBE"):
    value = normalized_email(email)
    if not value:
        return
    with transaction.atomic():
        SuppressedEmail.objects.get_or_create(email=value, defaults={"reason": reason})
        OutreachEmail.objects.filter(email__iexact=value, status="QUEUED").update(status="CANCELLED")
        Prospect.objects.filter(email__iexact=value).update(
            email_basis="NO", outreach_approved_at=None, outreach_approved_by=None
        )


def _smtp_email(item, lead):
    """A single approved message. No retries after an uncertain send outcome."""
    sender = os.environ["MOLI_OUTREACH_FROM"].strip()
    base = os.environ["MOLI_OUTREACH_PUBLIC_URL"].strip().rstrip("/")
    public_address = os.environ["MOLI_OUTREACH_POSTAL_ADDRESS"].strip()
    privacy_url = os.environ["MOLI_OUTREACH_PRIVACY_URL"].strip()
    token = unsubscribe_token(item.email)
    unsubscribe = base + "/yonetim/yurtdisi-musteriler/e-posta-cikis/" + quote(token, safe="") + "/"
    footer = (
        "\n\n---\nCommercial introduction from Moli Tekstil\n" + public_address
        + "\nPrivacy: " + privacy_url
        + "\nStop commercial emails: " + unsubscribe
    )
    email = EmailMessage(
        subject=item.subject,
        body=item.body.rstrip() + footer,
        from_email=sender,
        to=[item.email],
        headers={
            "List-Unsubscribe": "<" + unsubscribe + ">",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        connection=get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=os.environ["MOLI_OUTREACH_SMTP_HOST"],
            port=int(os.environ.get("MOLI_OUTREACH_SMTP_PORT", "587")),
            username=os.environ["MOLI_OUTREACH_SMTP_USER"],
            password=os.environ["MOLI_OUTREACH_SMTP_PASSWORD"],
            use_tls=True, use_ssl=False, timeout=15,
        ),
    )
    if email.send(fail_silently=False) != 1:
        raise RuntimeError("SMTP sunucusu gönderimi kabul etmedi.")


def process_outreach_queue(now=None):
    """Dispatch only explicitly approved, pre-reviewed leads. Safe by default."""
    enabled, dns_ready, missing = config_status()
    if not enabled or not dns_ready or missing:
        return {"status": "DISABLED", "sent": 0}
    now = timezone.localtime(now or timezone.now())
    if now.weekday() >= 5 or not (9 <= now.hour < 18):
        return {"status": "OUTSIDE_WINDOW", "sent": 0}
    try:
        limit = max(1, min(MAX_DAILY_EMAILS, int(os.environ.get("MOLI_OUTREACH_DAILY_LIMIT", "10"))))
    except ValueError:
        limit = 10
    today = now.date()
    already_sent = OutreachEmail.objects.filter(sent_at__date=today, status="SENT").count()
    remaining = max(0, limit - already_sent)
    sent = 0
    for _ in range(remaining):
        with transaction.atomic():
            queued = (OutreachEmail.objects.select_for_update(skip_locked=True)
                      .filter(status="QUEUED", scheduled_at__lte=timezone.now())
                      .select_related("prospect").order_by("scheduled_at", "id").first())
            if not queued:
                break
            lead = queued.prospect
            allowed, why = eligible(lead)
            initial = queued.kind == "INITIAL"
            if queued.email != normalized_email(lead.email):
                allowed, why = False, "İletişim adresi değişmiş; yeniden onay gerekir."
            if queued.kind == "FOLLOWUP" and lead.status in ("REPLIED", "QUALIFIED", "CUSTOMER", "REJECTED"):
                allowed, why = False, "Yanıt sonrası takip gönderimi iptal."
            if not allowed:
                queued.status = "CANCELLED"
                queued.error_message = why[:300]
                queued.save(update_fields=["status", "error_message"])
                continue
            queued.status = "SENDING"
            queued.save(update_fields=["status"])
        # Recheck unsubscribes immediately before network transfer.
        if SuppressedEmail.objects.filter(email=queued.email).exists():
            queued.status = "CANCELLED"
            queued.error_message = "İletişimden çıkma talebi."
            queued.save(update_fields=["status", "error_message"])
            continue
        try:
            _smtp_email(queued, lead)
        except Exception:
            logger.exception("Export email delivery failed for queue item %s", queued.pk)
            # An unclear SMTP outcome is never automatically retried.
            queued.status = "FAILED"
            queued.error_message = "E-posta teslimi doğrulanamadı; tekrar gönderim için manuel inceleme gerekir."
            queued.save(update_fields=["status", "error_message"])
            continue
        sent_at = timezone.now()
        queued.status = "SENT"
        queued.sent_at = sent_at
        queued.error_message = ""
        queued.save(update_fields=["status", "sent_at", "error_message"])
        if initial:
            Prospect.objects.filter(pk=lead.pk, status="APPROVED").update(
                status="CONTACTED", last_contacted_at=sent_at
            )
        sent += 1
    return {"status": "OK", "sent": sent}
