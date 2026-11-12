import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .automatic_search import PAGE_SIZE, SearchUnavailable, search_phrase
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
        self.assertContains(screen, "Sonraki 20 sonucu araştır")

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
        fake.return_value = self._result(1, 7)
        self._post()
        self._post()
        session = GuidedSearch.objects.get()
        self.assertTrue(session.exhausted)
        self.assertEqual(session.captured_count, 7)
        self.assertEqual(fake.call_count, 1)

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
