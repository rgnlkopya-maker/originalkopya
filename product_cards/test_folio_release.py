import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from core.models import Musteri, Order, UrunKod
from planning.models import ShipmentPlan
from .invoice_models import InvoiceDraft, InvoiceLine, StandaloneInvoice
from .models import ProductCard, ShowroomDraft, ShowroomDraftItem, ShowroomOrderLink
from .showroom_transfer_views import suspend_order_qr


class FolioReleaseTests(TestCase):
    release = date(2027, 1, 15)
    before = date(2027, 1, 14)

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("folio_release", password="test")
        self.client.force_login(self.user)
        self.customer = Musteri.objects.create(ad="Örnek Müşteri")
        self.product = UrunKod.objects.create(kod="FOLIO-RELEASE", urun_tipi="DIGER")
        self.card = ProductCard.objects.get(urun=self.product)
        self.folio = ShowroomDraft.objects.create(
            created_by=self.user, customer=self.customer, invoice_shipment_release_on=self.release,
            delivery_date=date(2027, 1, 22), status="APPROVED",
        )
        self.item = ShowroomDraftItem.objects.create(
            draft=self.folio, product_card=self.card, color="TAŞ", size="38", quantity=1, unit_price=100,
        )

    def order(self, release=None):
        with suspend_order_qr():
            return Order.objects.create(
                siparis_tipi="SERI", musteri=self.customer, urun_kodu=self.product.kod,
                renk="TAŞ", beden="38", adet=1, satis_fiyati=100, invoice_shipment_release_on=release,
            )

    def post(self, name, obj, **data):
        return self.client.post(reverse(name, args=[obj.pk]), data)

    def edit(self, **keys):
        values = dict(customer_id=self.customer.pk, items=[dict(
            urun_kodu=self.product.kod, anlasilan_fiyat="100",
            satirlar=[dict(renk="TAŞ", bedenler=["38"], adet=1)],
        )], **keys)
        return self.client.post(reverse("showroom_edit_save", args=[self.folio.pk]),
                                json.dumps(values), content_type="application/json")

    def test_unsaved_editor_round_trip(self):
        url = reverse("showroom_draft_autosave")
        response = self.client.post(url, json.dumps({
            "customer_id": self.customer.pk,
            "invoice_shipment_release_on": self.release.isoformat(),
            "delivery_date": "2027-01-22",
            "items": [{"urun_kodu": self.product.kod, "anlasilan_fiyat": 100,
                       "satirlar": [{"renk": "TAŞ", "bedenler": ["38"], "adet": 1}]}],
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("showroom_draft_action"),
                         json.dumps({"action": "save_draft"}), content_type="application/json")
        draft = ShowroomDraft.objects.exclude(pk=self.folio.pk).get()
        self.assertEqual(draft.status, "PENDING")
        self.assertEqual(draft.invoice_shipment_release_on, self.release)
        self.assertEqual(draft.delivery_date, date(2027, 1, 22))
        details = self.client.get(reverse("showroom_detail_page", args=[draft.pk]))
        self.assertContains(details, "15.01.2027")

    def test_transfer_carries_release_date_without_replacing_delivery_date(self):
        response = self.client.post(reverse("showroom_transfer_create", args=[self.folio.pk]),
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json()["created"], 1)
        order = self.folio.order_links.get().order
        self.assertEqual(order.invoice_shipment_release_on, self.release)
        self.assertEqual(order.teslim_tarihi, self.folio.delivery_date)

    def test_only_linked_orders_follow_changes_and_omitted_key_preserves_lock(self):
        linked = self.order(self.release)
        other = self.order()
        ShowroomOrderLink.objects.create(draft=self.folio, draft_item=self.item, order=linked)
        self.assertEqual(self.edit().status_code, 200)
        linked.refresh_from_db()
        self.assertEqual(linked.invoice_shipment_release_on, self.release)
        self.assertEqual(self.edit(invoice_shipment_release_on="bad").status_code, 400)
        self.assertEqual(self.edit(invoice_shipment_release_on="2027-01-19").status_code, 200)
        linked.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(linked.invoice_shipment_release_on, date(2027, 1, 19))
        self.assertIsNone(other.invoice_shipment_release_on)
        self.assertEqual(self.edit(invoice_shipment_release_on="").status_code, 200)
        linked.refresh_from_db()
        self.assertIsNone(linked.invoice_shipment_release_on)

    def test_lock_blocks_new_invoice_and_shipment_but_not_production(self):
        order = self.order(self.release)
        other = self.order()
        with patch("django.utils.timezone.localdate", return_value=self.before):
            response = self.post("invoice_add", order, planned_date=self.release.isoformat())
            self.assertEqual(response.status_code, 302)
            self.assertIn("15.01.2027", " ".join(str(m) for m in get_messages(response.wsgi_request)))
            self.assertFalse(InvoiceLine.objects.filter(order=order).exists())
            self.assertFalse(ShipmentPlan.objects.filter(order=order).exists())
            response = self.post("update_stage", order, stage="sevkiyat_durum", value="gonderildi")
            self.assertContains(response, "15.01.2027", status_code=400)
            self.assertFalse(order.events.filter(stage="sevkiyat_durum").exists())
            self.assertEqual(self.post("consignment_send_order", order, quantity=1).status_code, 400)
            self.assertEqual(self.post("update_stage", order, stage="kesim_durum", value="basladi").status_code, 200)
            self.assertTrue(order.events.filter(stage="kesim_durum", value="basladi").exists())
            self.post("invoice_add", other, planned_date=self.before.isoformat())
            self.assertTrue(InvoiceLine.objects.filter(order=other).exists())
            self.assertEqual(self.client.get(reverse("invoice_order_status", args=[order.pk])).json()["release_label"], "15.01.2027")
        with patch("django.utils.timezone.localdate", return_value=self.release):
            self.assertEqual(self.client.get(reverse("invoice_order_status", args=[order.pk])).json()["release_label"], "")
            self.post("invoice_add", order, planned_date=self.release.isoformat())
            self.assertTrue(InvoiceLine.objects.filter(order=order).exists())
            self.assertEqual(self.post("update_stage", order, stage="sevkiyat_durum", value="gonderildi").status_code, 200)
            self.assertTrue(order.events.filter(stage="sevkiyat_durum", value="gonderildi").exists())

    def test_bulk_manual_invoice_and_existing_invoice_cannot_bypass_lock(self):
        order = self.order(self.release)
        with patch("django.utils.timezone.localdate", return_value=self.before):
            response = self.client.post(reverse("standalone_invoice_create"), {
                "customer": self.customer.pk, "currency": "TRY", "invoice_date": self.release.isoformat(),
                "description": "Test", "quantity": 1, "unit": "Adet", "unit_price": "100",
                "vat_rate": "10", "order_id": order.pk,
            })
            self.assertEqual(response.status_code, 302)
            self.assertFalse(StandaloneInvoice.objects.exists())
            invoice = InvoiceDraft.objects.create(
                customer=self.customer, invoice_date=self.before, currency="TRY", created_by=self.user,
            )
            InvoiceLine.objects.create(invoice=invoice, order=order, price=100, vat_rate=10)
            self.assertEqual(self.post("invoice_finalize", invoice, official_number="TEST123").status_code, 403)
            self.assertFalse(InvoiceDraft.objects.filter(pk=invoice.pk, official_number="TEST123").exists())

    def test_order_detail_shows_both_restrictions(self):
        order = self.order(self.release)
        with patch("django.utils.timezone.localdate", return_value=self.before):
            page = self.client.get(reverse("order_detail", args=[order.pk]))
            self.assertContains(page, "15.01.2027 tarihine kadar faturaya aktarılamaz")
            self.assertContains(page, "15.01.2027 tarihine kadar sevk edilemez")
