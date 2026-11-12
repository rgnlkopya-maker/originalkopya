import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.utils import timezone

from .models import Prospect, SearchRun
from .research import canonical_url, draft_for, _candidate_from_result, process_daily_search
from .views import prospect_list


class ProspectResearchUnitTests(SimpleTestCase):
    def test_instagram_profiles_only(self):
        self.assertEqual(canonical_url("https://www.instagram.com/BoutiqueB/"), "https://instagram.com/boutiqueb")
        self.assertEqual(canonical_url("https://instagram.com/p/abc/"), "")
        self.assertEqual(canonical_url("https://instagram.com/reel/abc/"), "")
        self.assertEqual(canonical_url("javascript:alert(1)"), "")

    def test_domain_deduplication(self):
        self.assertEqual(
            canonical_url("https://www.example.com/bridal?utm_source=x"),
            canonical_url("https://example.com/evening-dresses"),
        )

    def test_retail_candidate_requires_relevant_evidence(self):
        row = {"title": "Formal Gowns Boutique", "url": "https://example.com/", "description": "Evening gowns in London"}
        result = _candidate_from_result(row, "GB")
        self.assertEqual(result["country"], "GB")
        self.assertEqual(result["status"], "NEW")
        self.assertIsNone(_candidate_from_result({**row, "title": "Software Company", "description": "Cloud ERP"}, "GB"))

    def test_draft_is_not_empty(self):
        self.assertIn("Moli Tekstil", draft_for("Sample Boutique", "DE"))
        self.assertIn("Moli Tekstil", draft_for("Sample Boutique", "FR"))
        self.assertIn("Moli Tekstil", draft_for("Sample Boutique", "GB"))


class ProspectResearchDBTests(TestCase):
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test-key"})
    @patch("sales_prospects.research._search_web")
    def test_daily_limit_and_no_repeat(self, search_mock):
        search_mock.return_value = [
            {
                "title": f"Evening Dress Boutique {i}",
                "url": f"https://boutique{i}.example.com/",
                "description": "Boutique for formal evening dresses",
            }
            for i in range(30)
        ]
        first = process_daily_search(manual=True)
        second = process_daily_search(manual=True)
        self.assertEqual(first["status"], "DONE")
        self.assertEqual(first["created"], 20)
        self.assertEqual(second["created"], 20)
        self.assertEqual(Prospect.objects.count(), 20)
        self.assertEqual(SearchRun.objects.count(), 1)
        self.assertEqual(search_mock.call_count, 1)

    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""})
    def test_disabled_without_approved_provider(self):
        self.assertEqual(process_daily_search(manual=True)["status"], "NOT_CONFIGURED")
        self.assertEqual(Prospect.objects.count(), 0)

    def test_staff_cannot_open_center(self):
        staff = get_user_model().objects.create_user(username="prospect_staff_test", password="unused")
        request = RequestFactory().get("/yonetim/yurtdisi-musteriler/")
        request.user = staff
        response = prospect_list(request)
        self.assertEqual(response.status_code, 403)
