from datetime import date, datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from core.models import UrunKod
from product_cards.models import ExchangeRate, ProductCard, ShowroomDraft, ShowroomDraftItem
from .siparis_finans_report_views import _folio_finance, _linked_cost_try


class SiparisFinansCurrencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("rapor-test", password="local-only")
        cls.card = ProductCard.objects.get(urun=UrunKod.objects.create(kod="T103"))
        ProductCard.objects.filter(pk=cls.card.pk).update(iscilik_maliyeti=D("2000"))
        cls.card.refresh_from_db()

    def setUp(self):
        self.client.force_login(self.user)

    def draft(self, currency, *, price="100.00", count=2, day=5, **fields):
        obj = ShowroomDraft.objects.create(created_by=self.user, currency=currency,
                                           status="APPROVED", **fields)
        # 21:30 UTC is already the next business date in İzmir.
        ShowroomDraft.objects.filter(pk=obj.pk).update(
            created_at=datetime(2026, 11, day - 1, 21, 30, tzinfo=timezone.utc)
        )
        obj.refresh_from_db()
        if price is not None:
            ShowroomDraftItem.objects.create(draft=obj, product_card=self.card,
                                              quantity=count, unit_price=D(price))
        return obj

    def test_foreign_revenue_and_tl_cost_match_on_report_list_and_detail(self):
        ExchangeRate.objects.create(rate_date=date(2026, 11, 4), usd_try=D("49"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 5), usd_try=D("50.026"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 6), usd_try=D("70"))
        fx = self.draft("USD", pricing_operations=[
            {"type": "DISCOUNT", "mode": "AMOUNT", "value": "10"},
            {"type": "VAT", "mode": "PERCENT", "value": "10"},
        ])
        self.draft("TRY", price="4000", count=1)
        expected = D("9504.94")
        with translation.override("tr"):
            report = self.client.get(reverse("siparis_finans_raporu"),
                                     {"start": "2026-11-05", "end": "2026-11-05"})
            listing = self.client.get(reverse("siparis_finans_foyleri"))
            detail = self.client.get(reverse("siparis_finans_foy_detay", args=[fx.pk]))
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.context["folio_summary"]["revenue"], expected + D("4000"))
        self.assertEqual(report.context["folio_summary"]["cost"], D("6000"))
        self.assertEqual(report.context["model_rows"][0]["revenue"], expected + D("4000"))
        self.assertContains(report, 'data-price="4501.65"', count=2)
        self.assertContains(report, 'data-cost="2000.00"', count=2)
        row = next(row for row in listing.context["rows"] if row["id"] == fx.pk)
        self.assertEqual(row["revenue"], expected)
        self.assertEqual(row["rate_day"], date(2026, 11, 5))
        finance = detail.context["finance"]
        self.assertEqual(finance["gross_total"], D("10455.43"))
        self.assertEqual(finance["profit"], D("5504.94"))
        self.assertEqual(finance["items"][0]["net_unit_price"], D("4752.47"))
        self.assertContains(detail, "TCMB arşiv kuru")
        self.assertEqual(ShowroomDraft.objects.get(pk=fx.pk).usd_try, D("1"))
        self.assertEqual(fx.items.get().unit_price, D("100"))

    def test_saved_rate_precedes_archive_and_weekend_uses_previous_valid_day(self):
        ExchangeRate.objects.create(rate_date=date(2026, 11, 4), usd_try=D("50"),
                                    eur_try=D("55"), gbp_try=D("65"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 5), usd_try=D("51"))
        eur = self.draft("EUR", eur_try=D("57.125"))
        self.assertEqual(_folio_finance(eur)["revenue"], D("11425"))
        self.assertEqual(_folio_finance(eur)["rate_source"], "Föy kuru")
        gbp = self.draft("GBP", day=7)
        self.assertEqual(_folio_finance(gbp)["revenue"], D("13000"))
        self.assertEqual(_folio_finance(gbp)["rate_day"], date(2026, 11, 4))

    def test_missing_rate_and_pending_ocr_are_flagged_not_treated_as_lira(self):
        ExchangeRate.objects.create(rate_date=date(2026, 10, 15), usd_try=D("48"))
        ExchangeRate.objects.create(rate_date=date(2026, 11, 6), usd_try=D("51"))
        missing = self.draft("USD")
        pending = self.draft("EUR", price=None, import_pending_items=[{"urun_kodu": "T103"}])
        report = self.client.get(reverse("siparis_finans_raporu"))
        self.assertEqual(report.context["folio_summary"]["count"], 0)
        self.assertEqual(report.context["model_rows"], [])
        self.assertContains(report, "Geçerli kur bulunamayan 1 dövizli föy")
        self.assertContains(report, "Fotoğraf kontrolü bekleyen 1 föy")
        detail = self.client.get(reverse("siparis_finans_foy_detay", args=[missing.pk]))
        self.assertEqual(detail.context["finance"]["native_revenue"], D("200"))
        self.assertIsNone(detail.context["finance"]["revenue"])
        self.assertIsNone(detail.context["finance"]["profit"])
        detail = self.client.get(reverse("siparis_finans_foy_detay", args=[pending.pk]))
        self.assertContains(detail, "Fotoğraf kontrolü bekliyor")

    def test_linked_cost_is_not_converted_at_the_sales_exchange_rate(self):
        ExchangeRate.objects.create(rate_date=date(2026, 11, 5), usd_try=D("50"))
        def cost(currency, day=5):
            return _linked_cost_try(SimpleNamespace(
                toplam_maliyet=D("100"), maliyet_para_birimi=currency,
                siparis_tarihi=date(2026, 11, day),
            ), {})
        self.assertEqual(cost("TRY"), D("100"))
        self.assertEqual(cost("USD"), D("5000"))
        self.assertIsNone(cost("EUR"))

    def test_folio_warning_clears_when_sale_and_cost_are_completed(self):
        draft = self.draft("TRY", price="0")
        ProductCard.objects.filter(pk=self.card.pk).update(iscilik_maliyeti=D("0"))
        listing = reverse("siparis_finans_foyleri")
        red = f'class="cardx folio-finance-missing" data-folio-id="{draft.pk}"'
        self.assertContains(self.client.get(listing), red)
        self.assertContains(self.client.get(listing), "Eksik bilgi: Satış fiyatı, Maliyet.")

        draft.items.update(unit_price=D("5000"))
        response = self.client.get(listing)
        self.assertContains(response, red)
        self.assertContains(response, "Eksik bilgi: Maliyet.")

        ProductCard.objects.filter(pk=self.card.pk).update(iscilik_maliyeti=D("2000"))
        response = self.client.get(listing)
        self.assertNotContains(response, red)
        self.assertContains(response, f'class="cardx" data-folio-id="{draft.pk}"')

    def test_missing_single_sale_price_is_flagged_even_with_positive_folio_total(self):
        draft = self.draft("TRY", price="4000", count=1)
        ShowroomDraftItem.objects.create(draft=draft, product_card=self.card, quantity=1, unit_price=D("0"))
        response = self.client.get(reverse("siparis_finans_foyleri"))
        self.assertContains(response, f'class="cardx folio-finance-missing" data-folio-id="{draft.pk}"')
        self.assertContains(response, "Eksik bilgi: Satış fiyatı.")
        self.assertEqual(response.context["rows"][0]["revenue"], D("4000"))

    def test_discount_to_zero_is_not_a_missing_sale_price(self):
        draft = self.draft("TRY", price="4000", count=1, discount_rate=D("100"))
        response = self.client.get(reverse("siparis_finans_foyleri"))
        self.assertContains(response, f'class="cardx" data-folio-id="{draft.pk}"')
        self.assertEqual(response.context["rows"][0]["revenue"], D("0"))
