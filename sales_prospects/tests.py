import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, RequestFactory
from django.utils import timezone

from .models import Prospect, SearchRun, OutreachEmail
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



class ExportOutreachSafetyTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username="export_manager_test", password="safe-test-pass")
        self.lead = Prospect.objects.create(
            name="North America Eveningwear Boutique", country="US",
            canonical_url="https://export-test.example.com",
            website_url="https://export-test.example.com",
            email="Sales@Example.com", contact_class="COMPANY", email_basis="US_B2B",
            email_source_note="Checked business website and business classification.",
            email_checked=True, message_draft="Hello, we make evening dresses. Moli Tekstil.",
            status="APPROVED",
        )

    def test_unapproved_company_cannot_enter_queue(self):
        from .outreach import queue_initial, eligible
        self.assertFalse(eligible(self.lead)[0])
        email, reason = queue_initial(self.lead, self.manager)
        self.assertIsNone(email)
        self.assertEqual(OutreachEmail.objects.count(), 0)

    def test_only_approved_contact_is_queued_once(self):
        from .outreach import queue_initial
        self.lead.outreach_approved_at = timezone.now()
        self.lead.outreach_approved_by = self.manager
        self.lead.save(update_fields=["outreach_approved_at", "outreach_approved_by"])
        msg, reason = queue_initial(self.lead, self.manager)
        again, duplicate = queue_initial(self.lead, self.manager)
        self.assertEqual(msg.pk, again.pk)
        self.assertEqual(OutreachEmail.objects.count(), 1)
        self.assertEqual(msg.email, "sales@example.com")

    def test_country_classification_does_not_auto_allow_uk_sole_trader(self):
        from .outreach import eligible
        self.lead.country = "GB"
        self.lead.contact_class = "PERSON"
        self.lead.email_basis = "GB_CORP"
        self.assertFalse(eligible(self.lead, require_approval=False)[0])

    def test_suppression_blocks_future_email(self):
        from .outreach import eligible, queue_initial, suppress
        self.lead.outreach_approved_at = timezone.now()
        self.lead.save(update_fields=["outreach_approved_at"])
        msg, _ = queue_initial(self.lead, self.manager)
        suppress("SALES@example.COM")
        msg.refresh_from_db()
        self.assertEqual(msg.status, "CANCELLED")
        self.assertFalse(eligible(self.lead)[0])

    @patch.dict(os.environ, {"MOLI_OUTREACH_ENABLED": ""})
    def test_dispatcher_is_off_by_default(self):
        from .outreach import process_outreach_queue
        self.assertEqual(process_outreach_queue()["status"], "DISABLED")

    def test_unsubscribe_link_is_a_signed_post_not_get(self):
        from .outreach import unsubscribe_token, normalized_email
        from django.urls import reverse
        from .models import SuppressedEmail
        token = unsubscribe_token("Sales@Example.com")
        url = reverse("prospect_unsubscribe", args=[token])
        view = self.client.get(url)
        self.assertEqual(view.status_code, 200)
        self.assertFalse(SuppressedEmail.objects.exists())
        result = self.client.post(url, data={"List-Unsubscribe": "One-Click"})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(SuppressedEmail.objects.filter(email="sales@example.com").exists())



class ExportSalesViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        from django.urls import reverse
        self.manager = get_user_model().objects.create_user(username="export_view_manager", password="safe-test-pass")
        group, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(group)
        self.client.force_login(self.manager)

    def test_management_screen_renders_with_email_tools(self):
        from django.urls import reverse
        response = self.client.get(reverse("prospect_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Toplu müşteri adayı")
        self.assertContains(response, "E-posta gönderimi kapalı")

    def test_csv_upload_adds_unapproved_leads_only(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse
        content = (
            "name,country,city,website,instagram,email,source_url\n"
            "Example Bridal Shop,US,Chicago,https://bridal-test.example.com,,info@bridal-test.example.com,https://bridal-test.example.com\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("leads.csv", content, content_type="text/csv")
        response = self.client.post(reverse("prospect_csv_import"), {"file": upload})
        self.assertEqual(response.status_code, 302)
        lead = Prospect.objects.get(name="Example Bridal Shop")
        self.assertFalse(lead.email_checked)
        self.assertEqual(lead.email_basis, "NONE")
        self.assertIsNone(lead.outreach_approved_at)
        self.assertEqual(OutreachEmail.objects.count(), 0)

    def test_manager_approval_creates_queue_without_sending(self):
        from django.urls import reverse
        lead = Prospect.objects.create(
            name="Approved Eveningwear", country="US",
            canonical_url="https://approved-export.example.com",
            website_url="https://approved-export.example.com",
            email="buyer@approved-export.example.com", contact_class="COMPANY",
            email_basis="US_B2B", email_checked=True,
            email_source_note="Manual corporate business review on company website.",
            message_draft="Hello! Moli Tekstil eveningwear.",
        )
        response = self.client.post(reverse("prospect_approve_outreach", args=[lead.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OutreachEmail.objects.count(), 1)
        msg = OutreachEmail.objects.get()
        self.assertEqual(msg.status, "QUEUED")
        self.assertIsNone(msg.sent_at)
