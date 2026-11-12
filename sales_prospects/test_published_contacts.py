"""Business contact parser regression tests based on publicly displayed layouts."""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from .contact_enrichment import extract_public_business_contacts
from .published_contacts import VisibleContacts, clean_phone, extract_number_from_text, schema_contacts


class PhoneParsingTests(SimpleTestCase):
    def test_german_impressum_phone_label(self):
        # Typical German Impressum layout.
        self.assertEqual(
            extract_number_from_text("crusz GmbH\nTel.: +49 30 96080500\nFax: +49 30 96080502"),
            "+493096080500",
        )

    def test_berlin_contact_page_standalone_mobile(self):
        html = (
            "<h2>Kontakt</h2><div><h3>0159 0629 1129</h3>"
            "<p>WhatsApp schreiben</p><h3>030 98377504</h3>"
            "<p>info@lafanta.de</p></div>"
        )
        parser = VisibleContacts(is_contact_page=True)
        parser.feed(html)
        contacts = parser.get_contacts()
        self.assertEqual(contacts["phone_number"], "015906291129")
        self.assertEqual(contacts["email"], "info@lafanta.de")

    def test_schema_business_telephone(self):
        json_data = (
            '{"@context":"https://schema.org","@type":"Store",'
            '"name":"Berlin Bridal Boutique","telephone":"+49 (30) 960 80 500",'
            '"email":"sales@bridal-shop.de"}'
        )
        found = schema_contacts(json_data)
        self.assertEqual(found["phone_number"], "+493096080500")
        self.assertEqual(found["email"], "sales@bridal-shop.de")

    def test_skip_address_and_product_codes(self):
        self.assertEqual(extract_number_from_text("Artikel 3019457000, Preis 2026.11 EUR"), "")
        self.assertEqual(extract_number_from_text("Spittelmarkt 11-12, 10117 Berlin"), "")
        self.assertEqual(clean_phone("1234"), "")

    @patch("sales_prospects.contact_enrichment.public_address", return_value="8.8.8.8")
    @patch("sales_prospects.contact_enrichment.safe_get")
    def test_follow_impressum_with_visible_phone(self, get, ip):
        get.side_effect = [
            (404, "", "text/plain"),
            (200, '<a href="/impressum">Impressum</a><h1>Evening Dress Boutique</h1>', "text/html"),
            (200, '<h1>Impressum</h1><p>Tel.: +49 30 96080500</p><p>Mail: service@boutique.de</p>', "text/html"),
            (404, "", "text/html"),
            (404, "", "text/html"),
        ]
        found = extract_public_business_contacts("https://boutique.de/")
        self.assertEqual(found.get("phone_number"), "+493096080500")
        self.assertEqual(found.get("phone_source_url"), "https://boutique.de/impressum")
        self.assertEqual(found.get("email"), "service@boutique.de")

    @patch("sales_prospects.contact_enrichment.public_address", return_value="8.8.8.8")
    @patch("sales_prospects.contact_enrichment.safe_get")
    def test_try_www_variant_if_bare_domain_redirects(self, get, ip):
        get.side_effect = [
            (301, "", ""),  # bare robots.txt redirect
            (404, "", "text/plain"),  # www robots.txt
            (200, '<h1>Abendmode Boutique</h1><p>Telefon: +49 30 96080500</p>', "text/html"),
            (404, "", "text/html"),
            (404, "", "text/html"),
            (404, "", "text/html"),
        ]
        found = extract_public_business_contacts("https://boutique.de")
        self.assertEqual(found["phone_number"], "+493096080500")
        self.assertEqual(found["phone_source_url"], "https://www.boutique.de/")

    @patch("sales_prospects.contact_enrichment.public_address", return_value="8.8.8.8")
    @patch("sales_prospects.contact_enrichment.safe_get")
    def test_robots_disallow_remains_respected(self, get, ip):
        get.return_value = (200, "User-agent: *\nDisallow: /\n", "text/plain")
        self.assertEqual(extract_public_business_contacts("https://boutique.de"), {})
        self.assertEqual(get.call_count, 1)
