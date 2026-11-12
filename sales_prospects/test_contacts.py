from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .contact_enrichment import (
    ContactLinks, business_host, extract_public_business_contacts,
    normalized_number, whatsapp_number, enrich_prospect_contact,
    scan_one_pending_prospect,
)
from .models import Prospect
from .forms import ProspectForm


class ContactExtractionTests(SimpleTestCase):
    def test_only_public_https_business_domains(self):
        self.assertEqual(business_host("http://fashion-store.com"), "")
        self.assertEqual(business_host("https://127.0.0.1/"), "")
        self.assertEqual(business_host("https://localhost/"), "")
        self.assertEqual(business_host("https://localhost.example/"), "")
        self.assertEqual(business_host("https://fashion-store.com:8080/"), "")
        self.assertEqual(business_host("https://instagram.com/boutique"), "")
        self.assertEqual(business_host("https://fashion-store.com/"), "fashion-store.com")

    def test_contact_parser_uses_explicit_business_links(self):
        html = (
            '<a href="mailto:sales@fashion-store.com">E-mail shop</a>'
            '<a href="tel:+49 (30) 1234 5678">Call the boutique</a>'
            '<a href="https://wa.me/491701234567">WhatsApp shop</a>'
            '<a href="https://www.instagram.com/atelier_eveningwear/">Instagram</a>'
            '<a href="/kontakt">Contact</a>'
            '<p>Private: +49 555 123 1234</p>'
        )
        parser = ContactLinks("https://fashion-store.com/", "fashion-store.com")
        parser.feed(html)
        self.assertEqual(parser.phone, "+493012345678")
        self.assertEqual(parser.email, "sales@fashion-store.com")
        self.assertEqual(parser.whatsapp, "491701234567")
        self.assertEqual(parser.instagram, "https://instagram.com/atelier_eveningwear")
        self.assertEqual(parser.contact_paths, ["/kontakt"])

    def test_whatsapp_number_needs_explicit_link(self):
        self.assertEqual(whatsapp_number("https://api.whatsapp.com/send?phone=447700900123"), "447700900123")
        self.assertEqual(whatsapp_number("https://instagram.com/handle"), "")
        self.assertEqual(normalized_number("123"), "")

    @patch("sales_prospects.contact_enrichment.public_address", return_value="8.8.8.8")
    @patch("sales_prospects.contact_enrichment.safe_get")
    def test_extract_two_public_pages_and_provenance(self, get, address):
        get.side_effect = [
            (404, "", "text/plain"),
            (200, '<a href="/contact">Contact</a><a href="https://instagram.com/Atelier123">Instagram</a>', "text/html"),
            (200, '<a href="mailto:orders@fashion-store.com">Email</a><a href="tel:+44 20 1234 5678">Shop telephone</a><a href="https://wa.me/447700900123">WhatsApp</a>', "text/html"),
        ]
        info = extract_public_business_contacts("https://fashion-store.com/")
        self.assertEqual(info["instagram_url"], "https://instagram.com/atelier123")
        self.assertEqual(info["instagram_source_url"], "https://fashion-store.com/")
        self.assertEqual(info["phone_number"], "+442012345678")
        self.assertEqual(info["phone_source_url"], "https://fashion-store.com/contact")
        self.assertEqual(info["whatsapp_number"], "447700900123")
        self.assertEqual(info["email"], "orders@fashion-store.com")
        self.assertEqual(info["email_source_url"], "https://fashion-store.com/contact")
        self.assertEqual(get.call_count, 3)

    @patch("sales_prospects.contact_enrichment.public_address", return_value="8.8.8.8")
    @patch("sales_prospects.contact_enrichment.safe_get")
    def test_disallow_robots_means_no_page_reads(self, get, address):
        get.return_value = (200, "User-agent: *\nDisallow: /\n", "text/plain")
        self.assertEqual(extract_public_business_contacts("https://fashion-store.com/"), {})
        self.assertEqual(get.call_count, 1)


class ContactWorkflowTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username="export_contacts_manager", password="pass12345")
        group, _ = Group.objects.get_or_create(name="patron")
        self.manager.groups.add(group)
        self.client.force_login(self.manager)
        self.lead = Prospect.objects.create(
            name="Public Eveningwear Boutique", country="GB",
            canonical_url="https://fashion-store.com",
            website_url="https://fashion-store.com",
            instagram_url="https://instagram.com/manual_handle",
            email="sales@fashion-store.com",
        )

    @patch("sales_prospects.contact_enrichment.extract_public_business_contacts")
    def test_scan_keeps_manually_entered_channels(self, extractor):
        extractor.return_value = {
            "email": "sales@fashion-store.com",
            "email_source_url": "https://fashion-store.com/contact",
            "phone_number": "+442012345678",
            "phone_source_url": "https://fashion-store.com/contact",
            "whatsapp_number": "447700900123",
            "whatsapp_source_url": "https://fashion-store.com/contact",
            "instagram_url": "https://instagram.com/other",
            "instagram_source_url": "https://fashion-store.com/",
        }
        self.assertEqual(enrich_prospect_contact(self.lead), 2)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.instagram_url, "https://instagram.com/manual_handle")
        self.assertEqual(self.lead.phone_number, "+442012345678")
        self.assertEqual(self.lead.whatsapp_number, "447700900123")
        self.assertEqual(self.lead.phone_source_url, "https://fashion-store.com/contact")

    @patch("sales_prospects.contact_enrichment.extract_public_business_contacts", return_value={})
    def test_scheduler_claims_one_shop_once(self, extractor):
        result = scan_one_pending_prospect()
        self.assertEqual(result["status"], "DONE")
        self.assertIsNotNone(self.lead.contact_scan_at or Prospect.objects.get(pk=self.lead.pk).contact_scan_at)
        result2 = scan_one_pending_prospect()
        self.assertEqual(result2["status"], "EMPTY")
        self.assertEqual(extractor.call_count, 1)

    @patch("sales_prospects.views.enrich_prospect_contact")
    def test_manager_can_scan_but_staff_cannot(self, enrich):
        enrich.return_value = 0
        route = reverse("prospect_scan_contacts", args=[self.lead.pk])
        response = self.client.post(route)
        self.assertEqual(response.status_code, 302)
        enrich.assert_called_once()
        self.client.logout()
        staff = get_user_model().objects.create_user(username="export_contacts_staff", password="pass12345")
        self.client.force_login(staff)
        self.assertEqual(self.client.post(route).status_code, 403)

    def test_phone_fields_are_in_form(self):
        form = ProspectForm(instance=self.lead)
        self.assertIn("phone_number", form.fields)
        self.assertIn("whatsapp_number", form.fields)
