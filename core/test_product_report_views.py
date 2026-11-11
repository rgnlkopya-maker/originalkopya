"""Regression tests for the read-only product performance report."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.template import engines
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from .product_report_views import (
    _valid_date, build_product_summary, product_performance_report,
)


def shipment(
    code, quantity, customer_id, customer_name, color,
    sale, cost, profit, *, kind="BALIK", order_type="SERI",
    shipped=date(2026, 11, 10), cost_recorded=True, final=True,
):
    order = SimpleNamespace(
        urun_kodu=code, urun_tipi=kind, adet=quantity,
        musteri_id=customer_id, musteri=SimpleNamespace(ad=customer_name),
        renk=color, siparis_tipi=order_type,
    )
    snapshot = SimpleNamespace(
        toplam_maliyet_tl=Decimal(str(cost)) if cost_recorded else None
    )
    return {
        "order": order, "ship_date": shipped,
        "result": {
            "snapshot": snapshot, "is_final": final,
            "satis_tl": Decimal(str(sale)), "maliyet_tl": Decimal(str(cost)),
            "kar_tl": Decimal(str(profit)),
        },
    }


class ProductReportTests(SimpleTestCase):
    def setUp(self):
        self.rows = [
            shipment(" 8091 balık ", 3, 1, "Moda", "Kırmızı", 1500, 900, 600),
            shipment("8091 BALIK", 2, 2, "Sitare", "Kırmızı", 1000, 0, 1000, cost_recorded=False, order_type="OZEL"),
            shipment("7119", 1, 2, "Sitare", "Lacivert", 200, 260, -60, kind="HELEN", order_type="TEKLI"),
        ]

    def test_report_groups_same_code_and_counts_units_not_order_rows(self):
        rows, totals = build_product_summary(self.rows)
        self.assertEqual([row["code"] for row in rows], ["8091 BALIK", "7119"])
        first = rows[0]
        self.assertEqual(first["orders"], 2)
        self.assertEqual(first["quantity"], 5)
        self.assertEqual(first["customer_count"], 2)
        self.assertEqual(first["top_customer"], "Moda")
        self.assertEqual(first["top_customer_units"], 3)
        self.assertEqual(first["top_color"], "KIRMIZI")
        self.assertEqual(first["top_color_units"], 5)
        self.assertEqual(first["seri"], 1)
        self.assertEqual(first["ozel"], 1)
        self.assertEqual(first["finance_missing"], 1)
        self.assertEqual(first["revenue"], Decimal("2500"))
        self.assertEqual(first["profit"], Decimal("1600"))
        self.assertEqual(first["margin"], Decimal("64"))
        self.assertEqual(totals["orders"], 3)
        self.assertEqual(totals["quantity"], 6)
        self.assertEqual(totals["finance_missing"], 1)
        self.assertEqual(totals["profit"], Decimal("1540"))
        self.assertTrue(rows[1]["in_loss"])

    def test_query_and_product_kind_filters(self):
        rows, totals = build_product_summary(self.rows, query="8091", product_type="BALIK")
        self.assertEqual(len(rows), 1)
        self.assertEqual(totals["quantity"], 5)
        rows, totals = build_product_summary(self.rows, product_type="HELEN")
        self.assertEqual([row["code"] for row in rows], ["7119"])
        self.assertEqual(totals["quantity"], 1)

    def test_bad_dates_are_safely_ignored(self):
        self.assertEqual(_valid_date("2026-11-10"), "2026-11-10")
        self.assertEqual(_valid_date("bad-date"), "")
        self.assertEqual(_valid_date("2026-02-30"), "")

    def test_route_and_template_resolve(self):
        self.assertEqual(
            reverse("product_performance_report"), "/reports/urun-performans/"
        )
        self.assertEqual(
            resolve("/reports/urun-performans/").func, product_performance_report
        )
        engines["django"].get_template("reports/product_performance.html")

    @patch("core.product_report_views.has_access", return_value=True)
    @patch("core.product_report_views.render", return_value=HttpResponse("ok"))
    @patch("core.product_report_views._shipment_finance_rows")
    def test_report_filters_date_and_renders_aggregates(self, financial_rows, render, can_view):
        financial_rows.return_value = self.rows
        request = RequestFactory().get(
            "/reports/urun-performans/",
            {"q": "8091", "type": "BALIK", "start": "2026-11-01", "end": "2026-11-30"},
        )
        request.user = SimpleNamespace(is_authenticated=True)
        response = product_performance_report(request)
        self.assertEqual(response.status_code, 200)
        financial_rows.assert_called_once_with(start="2026-11-01", end="2026-11-30")
        context = render.call_args.args[2]
        self.assertEqual(context["totals"]["quantity"], 5)
        self.assertEqual(context["totals"]["products"], 1)
        self.assertEqual(render.call_args.args[1], "reports/product_performance.html")

    @patch("core.product_report_views.has_access", return_value=False)
    def test_permission_denied(self, can_view):
        request = RequestFactory().get("/reports/urun-performans/")
        request.user = SimpleNamespace(is_authenticated=True)
        response = product_performance_report(request)
        self.assertEqual(response.status_code, 403)
