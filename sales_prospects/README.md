# MoliApp — Yurt Dışı Müşteri Merkezi

## Current workflow (November 2026)

Manager-only automated, page-by-page research for foreign eveningwear and
bridal retailers. The manager chooses country, city, and search words, then
clicks **20 mağaza sonucu araştır**. The server:

1. Calls a **third-party Google results provider, Serper.dev**, requesting
   up to 20 ordinary organic web results on the next results page. It does
   not scrape google.com directly or embed Google inside MoliApp.
2. Persists the country + city + phrase as a \`GuidedSearch\`.
3. Identical search terms on the next click resume page 2 (results 21–40),
   then page 3, and so on. Different terms start a separate research history.
   A search stops when the provider returns fewer than 20 organic results,
   or after the page cap. Search rankings can move over time.
4. Filters obviously irrelevant search results, stores new storefront domains
   or Instagram profile URLs as **unverified** prospects, and skips duplicates.
   The original search result source is tracked in \`GuidedSearchHit\`.
5. Shows a live CRM table for each search, with counts of reviewed results,
   new records, duplicates and skips, and all history sessions.
6. Uses the existing secured scheduler to enrich **one unscanned business
   website per tick**. It only reads published business links (mailto,
   tel, wa.me and Instagram) from that website's homepage and at most one
   contact page, when allowed by robots.txt.
7. Leaves unverified or unavailable email/phone/Instagram/follower values
   blank. Instagram follower count requires a lawful verified provider or
   authorized Meta API access; it is **not** obtained from Instagram scraping.
8. Never auto-sends email, Instagram DMs or WhatsApp messages just because
   contact details are found.

The Google-style SERP API is supplied by Serper (third-party, not an official
Google API). Serper's advertised starter plan includes 2,500 free queries,
subject to their current terms. **Do not request search results until**:

- Create a Serper account and obtain an API key.
- In Render web-service environment set \`SERPER_API_KEY\` to the secret.
- Deploy. Key must never be hardcoded into GitHub or visible in HTML.
- Verify the provider's contract supports the intended data handling.

The page clearly displays "Arama servisi bağlantısı eksik" and disables
the button when \`SERPER_API_KEY\` is not configured. No fake results are
generated. Google search itself remains accessible from the history entry
as a link for independent human verification.

### Operational notes

- Page size is 20 provider results, not a guaranteed 20 verified retail shops.
- One web search can yield fewer than 20 eligible results.
- Duplicate businesses seen on multiple pages are not added twice.
- Matching by domain/profile is conservative, not a perfect company matcher.
- Business email/phone enrichment happens in the existing scheduler, **not**
  synchronously for every result. It may take several scheduler ticks.
- Google search result order can change; the cursor is best effort.
- Current integrations do not have permission to retrieve arbitrary
  Instagram follower counts.
- Existing approved outbound-email engine remains OFF by default and
  uses separate manager consent/business-contact review.
- Previous manual bookmarklet / link selection interface was superseded;
  earlier prospect records are preserved.
- Previous daily 20-lead Brave scheduler was disabled, to avoid background
  search costs and unrelated client discovery.

## Other functionality

- Management menu: Yönetim → Yurt Dışı Müşteri Merkezi
- Manual prospect form and existing email/WhatsApp/Instagram detail buttons
- CSV import (UTF-8, at most 2,000 lines, 2 MB), with no auto-marketing
- User account role checks (patron/müdür)
- Contact detail source URL and status review
- E-mail approval queue, suppression list and signed opt-out endpoint

## Deploy and verification

Ensure Django migrations 0004, 0005 and 0006 are applied during the normal
MoliApp deployment, then run:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test sales_prospects --verbosity 2

For a production smoke test, enter a specific city and clothing niche, click
"20 mağaza sonucu araştır", verify the first page and search history. Click
again with identical terms, verify the next page and no duplicate lead IDs.
Check each selected website's contact source URL after enrichment. Do not
treat the presence of published business contact details as advertising consent.


## Business contact improvement (12 November 2026)
Research showed two common failure modes: unscanned candidates appeared with
empty phone cells, and the old crawler only recognized explicit \`tel:\` links
on at most two pages. The follow-up release now:
- Marks phone rows **Araştırılacak**, **Siteye erişilemedi** or **Bulunamadı**
  based on actual scan status, never assuming a blank equals "no phone exists".
- Reads the homepage plus up to three first-party contact/imprint URLs, using
  public page text, labelled phone fields, \`tel:\`, JSON-LD schema.org telephone,
  and already-supported WhatsApp/Instagram/mailto links.
- Recognizes public German telephone formats such as +49 30 96080500 and
  0159 0629 1129, without extracting arbitrary digit strings from product pages.
- Tries the www/non-www HTTPS hostname when one redirects, with validated
  public DNS, pinned TLS and **host-specific robots.txt** checks; external
  redirects and social media scraping remain disallowed.
- Rechecks existing legacy CRM records once after deployment and retries
  genuine fetch failures at most twice, six hours apart.
- Skips common directory/marketplace results (Yelp, Top10Berlin, Zalando,
  AboutYou and others) in future automated boutique searches. Existing
  records are not deleted.
- Does not send messages and never treats a found contact as marketing consent.
Any website that blocks automated access or does not publish a contact number
may still have an empty phone field. Check the recorded source URL for each
automatically filled contact.


## Unique prospect batches (13 November 2026)

**"20 yeni mağaza bul" now targets twenty *new* CRM prospects**, not the
first twenty Google entries. MoliApp checks each organic result against all
previously saved prospects, independent of search phrase, manager, country,
or the age of the old lead. A duplicate site-domain or a known Instagram
business profile never becomes a new prospect again.

The browser continues requesting the next Serper page automatically while
the target has not been met. To limit third-party API charges and avoid long
individual web-worker requests, each user click requests at most eight new
search pages. If the engine cannot find 20 unique stores within those pages,
it returns the actual number and the next click continues the investigation.

When only e.g. 3 new prospects are still needed, MoliApp stores just those
3. Unprocessed organic results from the current provider page are saved in
\`GuidedSearch.pending_results\` and examined first on the next click, without
charging for the same provider page a second time. The search history continues
to record cumulative reviewed, new, duplicate, and unsuitable results.

After 90 days without research on identical country/city/keywords, a new
search-history session starts from page 1 to reflect changed Google results.
Global CRM deduplication still excludes all previously found shops, including
those first discovered six months ago. Recent research sessions resume the
saved search cursor.

No API key is returned to the browser; only public search counts and CRM
results are returned. Automatic outreach remains disabled.
