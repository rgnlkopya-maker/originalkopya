# MoliApp — Yurt Dışı Müşteri Merkezi

This is an internal **lead research and CRM** module. It does not sign in to
Instagram, scrape Instagram, follow accounts or send Instagram DMs.

## Ready immediately

- Management menu: Yönetim → Yurt Dışı Müşteri Merkezi
- Patron / müdür only
- Manually create, search, review and update business prospects
- Website / Instagram links, source evidence and follow-up dates
- Curated EN/DE/FR/ES/IT first-contact drafts with one-click copy
- Contact status is **manual**, not proof that a DM was delivered
- Deduplication of business domains and indexed Instagram profile URLs

## Optional daily automated research (09:00 Europe/Istanbul)

An *approved web-search* provider is required. Configure the secret
`BRAVE_SEARCH_API_KEY` on the existing Render web service. Never paste an API
key into the repository, page HTML, or chat.

The existing authenticated minute scheduler calls
`sales_prospects.research.process_daily_search()`. It:
1. Does nothing without `BRAVE_SEARCH_API_KEY`.
2. Creates at most one run per local date after 09:00.
3. Rotates country-specific searches across 12 target markets.
4. Uses Brave Search's web index **only**, not Instagram scraping.
5. Saves at most 20 previously unseen, *unverified* businesses/day.
6. Doesn't invent empty results or auto-send any messages.
7. Allows a manager to retry a failed daily run manually.

Brave search API: `https://api.search.brave.com/res/v1/web/search`
(header `X-Subscription-Token`), HTTP requests and error handling remain
server-side. Provider subscriptions and fees are managed separately.

## Deployment

The new Django app `sales_prospects` has an initial migration. Ensure
`python manage.py migrate` runs before opening the page (using the existing
MoliApp migration/deploy procedure).

Check with:
```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test sales_prospects --verbosity 2
```

## Scope boundaries

The code never creates or edits a MoliApp order or accounting customer,
never sends Instagram DMs, and never treats a search result as a confirmed
wholesale retailer without review.
