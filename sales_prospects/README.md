# MoliApp — Yurt Dışı Müşteri Merkezi

Internal export sales CRM. The application **does not automate Instagram DMs,
WhatsApp messages or Google result scraping**. Nothing is emailed by default.

## Available

- Yönetim → Yurt Dışı Müşteri Merkezi (patron/müdür only).
- Review candidates by country, source and status.
- Import up to 2,000 candidates per UTF-8 CSV file (2 MB maximum) or add manually.
- Google search shortcuts for manual research.
- Website, Instagram and public source links.
- Separate public business phone, WhatsApp number and Instagram fields in the table and detail form.
- Each auto-detected channel includes the exact source page for verification.
- "Web sitesinden bilgileri bul" performs an on-demand scan of the business website.
- Existing scheduled tick enriches at most one unscanned HTTPS business site per invocation.
- Contact discovery only reads explicit tel:, wa.me, api.whatsapp.com and Instagram links
  from a retailer's own homepage and at most one contact page.
- HTTPS only, validates and pins public DNS addresses, disallows redirects,
  honors robots.txt, limits HTML bytes and does not fetch Instagram or WhatsApp.
- Explicit personal contact numbers are not inferred from unrelated text.
- Manual business numbers override automated discoveries. Unavailable data remains blank.
- UTF-8 CSV import accepts phone and whatsapp columns (also phone_number, whatsapp_number).

- Email, legal basis, company type and reviewer evidence on each prospect.
- Translated first-contact drafts (EN/DE/FR/ES/IT).
- Manager-reviewed initial email queue and one follow-up no sooner than 7 days.
- Global opt-out suppression. RFC 8058 one-click signed unsubscribe endpoint.
- Sending via authenticated SMTP, if and **only if** explicitly configured.
- Approved leads and emails are tracked separately from actual MoliApp customers.

## Sending is disabled until all checks are complete

Render service environment variables, without committing credentials:

- MOLI_OUTREACH_ENABLED=true — master switch, OFF by default.
- MOLI_OUTREACH_DNS_VERIFIED=true — only after SPF, DKIM and DMARC setup has been verified.
- MOLI_OUTREACH_FROM — verified sender address (e.g. export@company.example).
- MOLI_OUTREACH_SMTP_HOST, MOLI_OUTREACH_SMTP_PORT=587
- MOLI_OUTREACH_SMTP_USER, MOLI_OUTREACH_SMTP_PASSWORD
- MOLI_OUTREACH_POSTAL_ADDRESS — actual business postal address, included in mail.
- MOLI_OUTREACH_PUBLIC_URL — HTTPS root URL hosting unsubscribe endpoint.
- MOLI_OUTREACH_PRIVACY_URL — public URL explaining data processing.
- MOLI_OUTREACH_DAILY_LIMIT — defaults to 10, max 25 per local day.

The authenticated existing scheduler dispatches only on business days,
09:00–18:00 Europe/Istanbul. Each first contact needs explicit manager approval.
Unknown or blocked email basis is always rejected.

Allowed contact basis in this initial workflow:
- Explicit marketing consent with documented evidence (all countries).
- US: reviewed business company/contact for relevant B2B promotion.
- GB: confirmed corporate subscriber/company with documented review.
Sole traders in GB are *not* automatically eligible under the corporate basis.
These technical gates do not replace jurisdiction-specific legal review.

Delivery failures are **not retried automatically**, since a failed SMTP
request can have an uncertain outcome. "Sent" means the provider accepted
the message, not that the recipient read or received it.

## What is not yet available

- Fully automated prospect discovery from free Google searches.
- Automatic validation of company registration, consent or email deliverability.
- Universal discovery of Instagram profiles or phone numbers where none are published by the business.
- Phone/mobile classification without explicit source evidence (tel: can be a landline).
- Automatic reply classification / inbox sync.
- Automatically generated follow-ups without review.
- Automated outreach to a thousand recipients daily.

The previous optional Brave Search connector remains disabled unless its
approved API key is deliberately configured; the visible interface does not
require it. A different properly licensed business source can replace it.

## Migration and checks

The production web service has an existing migration-on-build setup.
Run the usual production deploy, then:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test sales_prospects --verbosity 2

Do not activate sending before confirming the sender address, business contact
data source, country-specific legal requirements and unsubscribe behavior.
