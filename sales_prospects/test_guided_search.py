import json
import os
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .automatic_search import PAGE_SIZE, SearchUnavailable, search_phrase, run_next_page, find_or_start
from .guided_search import canonical_store_url, google_url_for
from .models import GuidedSearch, GuidedSearchHit, Prospect


class SequentialResearchUnitTests(SimpleTestCase):
    def test_search_language_and_country(self):
        self.assertIn("Germany", search_phrase("evening dress boutique", "DE", "Berlin"))
        self.assertIn("Berlin", google_url_for("evening dress boutique", "DE", "Berlin"))

    def test_reject_nonbusiness_links(self):
        for url in ("https://google.com/search?q=x", "http://localhost/",
                    "https://youtube.com/watch?v=1", "https://127.0.0.1/",
                    "https://instagram.com/p/example/"):
            self.assertFalse(canonical_store_url(url))
        self.assertEqual(canonical_store_url("https://www.example-boutique.com/dresses"),
                         "https://example-boutique.com")


class SequentialResearchTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username="auto_export_manager", password="test-password"
        )
        group, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(group)
        self.client.force_login(self.manager)

    def _post(self, city="Berlin", query="evening dress boutique"):
        return self.client.post(reverse("prospect_automatic_batch"), {
            "country": "DE", "city": city, "query": query,
        })

    @staticmethod
    def _result(page, count=20):
        return [
            {"title": f"Eveningwear Boutique {page}-{i}", "link": f"https://shop{page}{i}.example.com/",
             "snippet": "Boutique retail store with elegant evening gowns"}
            for i in range(count)
        ]

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_first_and_second_click_continue_next_twenty(self, fake):
        fake.side_effect = [self._result(1), self._result(2)]
        self.assertEqual(self._post().status_code, 302)
        self.assertEqual(self._post().status_code, 302)
        fake.assert_any_call("dummy-test", "evening dress boutique", "DE", "Berlin", 1)
        fake.assert_any_call("dummy-test", "evening dress boutique", "DE", "Berlin", 2)
        self.assertEqual(GuidedSearch.objects.count(), 1)
        session = GuidedSearch.objects.get()
        self.assertEqual(session.next_page, 3)
        self.assertEqual(session.captured_count, 40)
        self.assertEqual(session.added_count, 40)
        self.assertEqual(GuidedSearchHit.objects.count(), 40)
        self.assertEqual(Prospect.objects.count(), 40)
        self.assertEqual(fake.call_count, 2)
        screen = self.client.get(reverse("prospect_list_with_history", args=[session.pk]))
        self.assertContains(screen, "Arama geçmişi")
        self.assertContains(screen, "20 yeni mağaza bul")

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_identical_business_cannot_be_added_twice(self, fake):
        fake.side_effect = [
            [{"title": "Bridal Boutique Vienna", "link": "https://bridal-shop.example.com",
              "snippet": "Boutique eveningwear dress shop"} for _ in range(20)],
            self._result(2),
        ]
        self._post()
        self.assertEqual(Prospect.objects.count(), 1)
        session = GuidedSearch.objects.get()
        self.assertEqual(session.added_count, 1)
        self.assertGreater(session.skipped_count, 0)

        self._post(city="Munich")
        self.assertEqual(GuidedSearch.objects.count(), 2)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_short_page_marks_search_exhausted(self, fake):
        fake.side_effect = [self._result(1, 7), []]
        self._post()
        self._post()
        session = GuidedSearch.objects.get()
        self.assertTrue(session.exhausted)
        self.assertEqual(session.captured_count, 7)
        self.assertEqual(fake.call_count, 2)

    @patch.dict(os.environ, {"SERPER_API_KEY": ""})
    def test_no_api_key_does_not_create_fabricated_results(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Prospect.objects.count(), 0)
        self.assertEqual(GuidedSearch.objects.count(), 0)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_failure_does_not_advance_page(self, fake):
        fake.side_effect = [SearchUnavailable("Servis bağlantı hatası"), self._result(1)]
        self._post()
        self.assertEqual(GuidedSearch.objects.get().next_page, 1)
        self._post()
        self.assertEqual(GuidedSearch.objects.get().next_page, 2)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_no_automatic_outreach_is_authorized(self, fake):
        from .models import OutreachEmail
        fake.return_value = self._result(1)
        self._post()
        lead = Prospect.objects.first()
        self.assertEqual(lead.status, "NEW")
        self.assertEqual(lead.email_basis, "NONE")
        self.assertFalse(lead.email_checked)
        self.assertIsNone(lead.instagram_followers)
        self.assertEqual(OutreachEmail.objects.count(), 0)

    def test_staff_cannot_start_search(self):
        self.client.logout()
        staff = get_user_model().objects.create_user(
            username="auto_export_staff", password="test-password"
        )
        self.client.force_login(staff)
        self.assertEqual(self._post().status_code, 403)


class UniqueTwentyProspectTests(TestCase):
    """Same click skips previously saved shops and keeps pagination exact."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="unique_search_manager", password="unique-test-password"
        )
        group, _ = Group.objects.get_or_create(name="patron")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def _create_search(self, query="evening gown boutique", city="Berlin"):
        return GuidedSearch.objects.create(
            created_by=self.user, country="DE", city=city, query=query,
            google_url=google_url_for(query, "DE", city),
        )

    @staticmethod
    def _results(page):
        return [
            {"title": f"Bridal Eveningwear Boutique {page}-{i}",
             "link": f"https://bridalshop{page}-{i}.example.com/",
             "snippet": "Wedding and formal dress boutique retailer"}
            for i in range(20)
        ]

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_skips_20_existing_leads_then_fills_next_20_on_same_click(self, fake):
        fake.side_effect = [self._results(1), self._results(2)]
        for item in self._results(1):
            canonical = item["link"].rstrip("/")
            Prospect.objects.create(
                name=item["title"], canonical_url=canonical,
                website_url=canonical, country="DE",
            )
        search = self._create_search()
        url = reverse("prospect_automatic_batch")
        payload = {"country": "DE", "city": "Berlin", "query": search.query, "target_new": 20}
        first = self.client.post(url, payload, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["new"], 0)
        self.assertEqual(first.json()["duplicates"], 20)
        self.assertEqual(first.json()["pages_fetched"], 1)
        second = self.client.post(url, payload, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["new"], 20)
        self.assertEqual(second.json()["duplicates"], 0)
        self.assertEqual(Prospect.objects.count(), 40)
        search.refresh_from_db()
        self.assertEqual(search.captured_count, 40)
        self.assertEqual(search.duplicate_count, 20)
        self.assertEqual(search.added_count, 20)
        self.assertEqual(search.next_page, 3)
        # Old prospects are never surfaced in the new search results.
        self.assertEqual(GuidedSearchHit.objects.filter(search=search).count(), 20)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_preserves_extra_results_when_only_two_new_shops_are_needed(self, fake):
        fake.return_value = self._results(1)
        search = self._create_search()
        first = run_next_page(search, self.user, target_new=2)
        self.assertEqual(first["new"], 2)
        self.assertEqual(first["seen"], 2)
        search.refresh_from_db()
        self.assertEqual(search.next_page, 2)
        self.assertEqual(len(search.pending_results), 18)
        next_batch = run_next_page(search, self.user, target_new=18)
        self.assertEqual(next_batch["new"], 18)
        self.assertEqual(next_batch["pages_fetched"], 0)
        search.refresh_from_db()
        self.assertEqual(len(search.pending_results), 0)
        self.assertEqual(search.added_count, 20)
        self.assertEqual(fake.call_count, 1)
        self.assertEqual(Prospect.objects.count(), 20)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_search_history_cross_search_duplicates_not_added_again(self, fake):
        fake.side_effect = [self._results(1), self._results(1), self._results(2)]
        search1 = self._create_search(query="Abendmode Berlin")
        self.assertEqual(run_next_page(search1, self.user)["new"], 20)
        search2 = self._create_search(query="formal evening gowns Berlin")
        self.assertEqual(run_next_page(search2, self.user)["duplicates"], 20)
        self.assertEqual(run_next_page(search2, self.user)["new"], 20)
        self.assertEqual(Prospect.objects.count(), 40)
        self.assertEqual(search1.hits.count(), 20)
        self.assertEqual(search2.hits.count(), 20)

    def test_search_restarts_only_when_old_not_recent(self):
        old = self._create_search(query="evening dress boutique")
        GuidedSearch.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=180),
            last_import_at=timezone.now() - timedelta(days=180),
        )
        fresh = find_or_start(self.user, "DE", " Berlin ", "  evening  dress boutique ")
        self.assertNotEqual(fresh.pk, old.pk)
        again = find_or_start(self.user, "DE", "Berlin", "evening dress boutique")
        self.assertEqual(fresh.pk, again.pk)
        self.assertEqual(GuidedSearch.objects.count(), 2)

    @patch.dict(os.environ, {"SERPER_API_KEY": "dummy-test"})
    @patch("sales_prospects.automatic_search._fetch_serper_page")
    def test_empty_provider_page_marks_results_completed(self, fake):
        fake.return_value = []
        search = self._create_search()
        result = run_next_page(search, self.user)
        self.assertTrue(result["exhausted"])
        self.assertEqual(result["seen"], 0)
        self.assertEqual(run_next_page(search, self.user)["status"], "EXHAUSTED")
        self.assertEqual(fake.call_count, 1)

    def test_workspace_explains_twenty_new_not_twenty_results(self):
        response = self.client.get(reverse("prospect_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20 yeni mağaza bul")
        self.assertContains(response, "MAX_PAGES_PER_CLICK = 8")
