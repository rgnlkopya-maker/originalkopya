"""Regression tests for folio date updates (no external writes)."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Musteri, Order, OrderEvent, UrunKod
from .models import ProductCard, ShowroomDraft, ShowroomDraftItem, ShowroomOrderLink
from .showroom_transfer_views import suspend_order_qr


class ShowroomDeliveryDateTests(TestCase):
    old_date = date(2026, 12, 4)
    new_date = date(2026, 12, 11)
    independent_date = date(2026, 12, 18)

    def setUp(self):
        self.patron, _ = Group.objects.get_or_create(name="patron")
        self.user = get_user_model().objects.create_user(username="folio-date-owner")
        self.user.groups.add(self.patron)
        self.client.force_login(self.user)
        self.customer = Musteri.objects.create(ad="Teslim Tarihi Test")
        self.product = UrunKod.objects.create(kod="DELIVERY-TEST", urun_tipi="DIGER")
        self.card, _ = ProductCard.objects.get_or_create(urun=self.product)
        self.folio = ShowroomDraft.objects.create(
            created_by=self.user, customer=self.customer, status="APPROVED",
            delivery_date=self.old_date,
        )
        self.item = ShowroomDraftItem.objects.create(
            draft=self.folio, product_card=self.card, color="Taş", size="38",
            quantity=1, unit_price=Decimal("100.00"),
        )
        self.url = reverse("showroom_edit_save", args=[self.folio.pk])

    def order(self, *, linked=True, delivery_date=old_date, **fields):
        with suspend_order_qr():
            order = Order.objects.create(
                siparis_tipi="SERI", musteri=self.customer, urun_kodu=self.product.kod,
                renk="Taş", beden="38", adet=1, teslim_tarihi=delivery_date,
                satis_fiyati=Decimal("100.00"), **fields,
            )
        if linked:
            ShowroomOrderLink.objects.create(draft=self.folio, draft_item=self.item, order=order)
        return order

    def save(self, new_date=new_date.isoformat(), *, omit_date=False):
        payload = {
            "customer_id": self.customer.pk,
            "items": [{
                "urun_kodu": self.product.kod,
                "anlasilan_fiyat": "100.00",
                "satirlar": [{"renk": "Taş", "bedenler": ["38"], "adet": 1}],
            }],
        }
        if not omit_date:
            payload["delivery_date"] = new_date
        return self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

    def test_transferred_folio_date_change_reaches_order_and_audit(self):
        transfer = self.client.post(
            reverse("showroom_transfer_create", args=[self.folio.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(transfer.status_code, 200)
        self.assertEqual(transfer.json()["created"], 1)
        order = self.folio.order_links.get().order
        self.assertEqual(order.teslim_tarihi, self.old_date)

        response = self.save()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery_dates_synced"], 1)
        self.assertIn("1 bağlı siparişin teslim tarihi güncellendi", response.json()["message"])
        self.folio.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.folio.delivery_date, self.new_date)
        self.assertEqual(order.teslim_tarihi, self.new_date)
        audit = order.events.get(event_type="order_update", stage="teslim_tarihi")
        self.assertEqual(audit.user, self.user.username)
        self.assertEqual(audit.old_value, self.old_date.isoformat())
        self.assertEqual(audit.new_value, self.new_date.isoformat())

    def test_different_dates_shipped_inactive_and_unlinked_are_preserved(self):
        normal = self.order()
        override = self.order(delivery_date=self.independent_date)
        cleared_individually = self.order(delivery_date=None)
        shipped_status = self.order(sevkiyat_durum="gonderildi")
        shipped_timestamp = self.order(sevkiyat_tarihi=timezone.now())
        previously_shipped = self.order()
        OrderEvent.objects.bulk_create([
            OrderEvent(order=previously_shipped, user="test", stage="sevkiyat_durum", value="gonderildi"),
            OrderEvent(order=previously_shipped, user="test", stage="sevkiyat_durum", value="iade_geldi"),
        ])
        inactive = self.order(is_active=False)
        unlinked = self.order(linked=False)
        ShowroomOrderLink.objects.create(draft=self.folio, draft_item=self.item, order=None)

        response = self.save()

        self.assertEqual(response.json()["delivery_dates_synced"], 1)
        normal.refresh_from_db()
        self.assertEqual(normal.teslim_tarihi, self.new_date)
        for order, expected in (
            (override, self.independent_date), (cleared_individually, None),
            (shipped_status, self.old_date), (shipped_timestamp, self.old_date),
            (previously_shipped, self.old_date), (inactive, self.old_date), (unlinked, self.old_date),
        ):
            with self.subTest(order=order.pk):
                order.refresh_from_db()
                self.assertEqual(order.teslim_tarihi, expected)
                self.assertFalse(order.events.filter(event_type="order_update", stage="teslim_tarihi").exists())

    def test_existing_links_survive_date_sync_when_folio_is_back_in_pending(self):
        self.folio.status = "PENDING"
        self.folio.orders_created = True
        self.folio.save(update_fields=["status", "orders_created"])
        order = self.order()

        response = self.save()

        self.assertEqual(response.json()["delivery_dates_synced"], 1)
        self.folio.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.folio.status, "PENDING")
        self.assertEqual(order.teslim_tarihi, self.new_date)

    def test_setting_a_previously_blank_date_and_explicitly_clearing_it(self):
        self.folio.delivery_date = None
        self.folio.save(update_fields=["delivery_date"])
        order = self.order(delivery_date=None)

        response = self.save()
        self.assertEqual(response.json()["delivery_dates_synced"], 1)
        order.refresh_from_db()
        self.assertEqual(order.teslim_tarihi, self.new_date)

        response = self.save("")
        self.assertEqual(response.json()["delivery_dates_synced"], 1)
        self.folio.refresh_from_db()
        order.refresh_from_db()
        self.assertIsNone(self.folio.delivery_date)
        self.assertIsNone(order.teslim_tarihi)

    def test_unchanged_or_omitted_date_does_not_overwrite_orders(self):
        order = self.order()
        different = self.order(delivery_date=self.independent_date)

        self.assertEqual(self.save(self.old_date.isoformat()).json()["delivery_dates_synced"], 0)
        self.assertEqual(self.save(omit_date=True).json()["delivery_dates_synced"], 0)

        for obj, attr, expected in (
            (self.folio, "delivery_date", self.old_date), (order, "teslim_tarihi", self.old_date),
            (different, "teslim_tarihi", self.independent_date),
        ):
            obj.refresh_from_db()
            self.assertEqual(getattr(obj, attr), expected)
        self.assertFalse(OrderEvent.objects.filter(event_type="order_update", stage="teslim_tarihi").exists())

    def test_other_manager_cannot_change_folio_or_linked_order(self):
        order = self.order()
        other = get_user_model().objects.create_user(username="other-folio-manager")
        other.groups.add(self.patron)
        self.client.force_login(other)

        self.assertEqual(self.save().status_code, 404)
        self.folio.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.folio.delivery_date, self.old_date)
        self.assertEqual(order.teslim_tarihi, self.old_date)

    def test_order_audit_failure_rolls_back_folio_and_order_dates(self):
        order = self.order()
        with patch("product_cards.showroom_views.OrderEvent.objects.bulk_create", side_effect=RuntimeError("audit write failed")):
            with self.assertRaisesMessage(RuntimeError, "audit write failed"):
                self.save()

        self.folio.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.folio.delivery_date, self.old_date)
        self.assertEqual(order.teslim_tarihi, self.old_date)
