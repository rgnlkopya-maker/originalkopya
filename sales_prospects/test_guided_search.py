import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .guided_search import canonical_store_url, google_url_for, normalized_results
from .models import GuidedSearch, GuidedSearchHit, Prospect


class GuidedResearchUnitTests(SimpleTestCase):
    def test_google_search_is_a_user_visible_browser_url(self):
        url = google_url_for("evening dress boutique", "DE", "Berlin")
        self.assertTrue(url.startswith("https://www.google.com/search?"))
        self.assertIn("Berlin", url)
        self.assertIn("Almanya", url)

    def test_blocks_search_engines_and_local_links(self):
        for url in (
            "https://google.com/search?q=x",
            "https://www.google.com/url?q=https://shop.com",
            "http://localhost:8080",
            "https://127.0.0.1/",
            "ftp://boutique.com/",
            "javascript:alert(1)",
            "https://instagram.com/p/xyz/",
            "https://youtube.com/watch?v=123",
        ):
            self.assertFalse(canonical_store_url(url), url)
        self.assertEqual(canonical_store_url("https://www.boutique-example.com/dresses"),
                         "https://boutique-example.com")
        self.assertEqual(canonical_store_url("https://instagram.com/ShopExample/"),
                         "https://instagram.com/shopexample")

    def test_plain_url_and_named_url_paste(self):
        items = normalized_results(
            "https://boutique-one.com/\nFancy Dress Shop | https://boutique-two.com/"
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["name"], "Fancy Dress Shop")

    def test_batch_is_bounded(self):
        with self.assertRaises(ValueError):
            normalized_results(json.dumps([{"url": "https://example.com"}] * 51))


class GuidedResearchWorkflowTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username="export_guided_manager", password="safe-password")
        group, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(group)
        self.client.force_login(self.manager)

    def _start(self, query="evening dress boutique"):
        response = self.client.post(
            reverse("prospect_guided_start"),
            {"query": query, "country": "DE", "city": "Berlin"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        return GuidedSearch.objects.get()

    def test_search_is_recorded_even_before_import(self):
        search = self._start()
        self.assertEqual(search.country, "DE")
        self.assertIn("Berlin", search.google_url)
        self.assertEqual(search.added_count, 0)
        page = self.client.get(reverse("prospect_list"))
        self.assertContains(page, "Arama Geçmişi")
        self.assertContains(page, "evening dress boutique")
        self.assertContains(page, "MoliApp'e Aktar")

    def test_approved_selected_links_are_imported_and_deduplicated(self):
        search = self._start()
        links = [
            {"name": "Berlin Evening Dress Boutique", "url": "https://boutique-one.example.com/evening"},
            {"name": "Example Bridal Studio", "url": "https://studio-two.example.com"},
            {"name": "Duplicate Path", "url": "https://boutique-one.example.com/contact"},
            {"name": "Invalid Google Result", "url": "https://google.com/search?q=shop"},
        ]
        response = self.client.post(
            reverse("prospect_guided_import"),
            {"search_id": search.pk, "results_json": json.dumps(links)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Prospect.objects.count(), 2)
        self.assertEqual(GuidedSearchHit.objects.count(), 2)
        search.refresh_from_db()
        self.assertEqual(search.added_count, 2)
        self.assertEqual(search.skipped_count, 2)
        self.assertEqual(search.captured_count, 4)
        lead = Prospect.objects.get(name="Berlin Evening Dress Boutique")
        self.assertEqual(lead.status, "NEW")
        self.assertEqual(lead.email_basis, "NONE")
        self.assertFalse(lead.email_checked)
        self.assertEqual(lead.country, "DE")

        page = self.client.get(reverse("prospect_list_with_history", args=[search.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Berlin Evening Dress Boutique")

    def test_repeated_search_keeps_old_history_without_duplicate_leads(self):
        first = self._start()
        payload = json.dumps([{"name":"Boutique One","url":"https://boutique1.example.com"}])
        self.client.post(reverse("prospect_guided_import"),
                         {"search_id": first.pk, "results_json": payload})
        second = GuidedSearch.objects.create(
            created_by=self.manager, country="DE", city="Munich",
            query="formalwear store",
            google_url=google_url_for("formalwear store", "DE", "Munich"),
        )
        self.client.post(reverse("prospect_guided_import"),
                         {"search_id": second.pk, "results_json": payload})
        self.assertEqual(Prospect.objects.count(), 1)
        self.assertEqual(GuidedSearchHit.objects.count(), 2)
        second.refresh_from_db()
        self.assertEqual(second.duplicate_count, 1)

    def test_plain_pasted_urls_work_without_google_helper(self):
        search = self._start()
        response = self.client.post(
            reverse("prospect_guided_import"),
            {"search_id": search.pk, "result_urls": "Fancy Boutique | https://fancy.example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Prospect.objects.filter(name="Fancy Boutique").exists())

    def test_permission_to_search_and_import_is_restricted(self):
        self.client.logout()
        staff = get_user_model().objects.create_user(username="export_guided_staff", password="safe-password")
        self.client.force_login(staff)
        self.assertEqual(self.client.post(
            reverse("prospect_guided_start"),
            {"query":"bridal stores", "country":"DE", "city":"Berlin"},
        ).status_code, 403)
        self.assertEqual(self.client.post(reverse("prospect_guided_import"),
                         {"search_id": 1, "result_urls": "https://example.com"}).status_code, 403)

    def test_cannot_import_into_another_managers_search(self):
        search = self._start()
        manager2 = get_user_model().objects.create_user(username="export_other_manager", password="safe-password")
        group = Group.objects.get(name="patron")
        manager2.groups.add(group)
        self.client.force_login(manager2)
        response = self.client.post(
            reverse("prospect_guided_import"),
            {"search_id": search.pk, "result_urls": "https://another.example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Prospect.objects.count(), 0)
