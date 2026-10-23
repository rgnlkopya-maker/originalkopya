"""Pure Paraşüt sales invoice preparation. No HTTP or e-document functions."""
from decimal import Decimal
from .invoice_models import ParasutCustomerMapping, ParasutProductMapping

CURRENCY = {"TRY": "TRL", "TL": "TRL", "USD": "USD", "EUR": "EUR", "GBP": "GBP"}


def build_parasut_sales_invoice(invoice, product_ids=None):
    product_ids = product_ids or {}
    problems = []
    if invoice.parasut_manual_recorded:
        problems.append("Paraşüt'te elle işlendi olarak işaretlenmiş.")
    contact = ParasutCustomerMapping.objects.filter(customer=invoice.customer).first()
    if not contact:
        problems.append("Paraşüt cari eşleştirmesi eksik.")
    currency = CURRENCY.get(invoice.currency)
    if not currency:
        problems.append("Para birimi Paraşüt'te desteklenmiyor.")
    detail = getattr(invoice.customer, "customer_detail", None)
    address = ((getattr(detail, "fatura_adresi", "") or "").strip() or
               (getattr(detail, "adres", "") or "").strip())
    if not address:
        problems.append("Müşteri kartında fatura adresi eksik.")
    lines = list(invoice.lines.select_related("order").order_by("id"))
    if not lines:
        problems.append("Faturada ürün yok.")
    items = []
    for line in lines:
        code = str(line.order.urun_kodu or "").strip()
        product = ParasutProductMapping.objects.filter(product_code=code).first() if code not in product_ids else None
        product_id = product_ids.get(code) or (product.external_product_id if product else None)
        if not product_id:
            problems.append("Paraşüt ürünü henüz hazırlanmadı: " + code[:70])
            continue
        price = Decimal(line.price)
        rate = Decimal(line.vat_rate)
        if rate != Decimal("10"):
            problems.append("Paraşüt aktarımı yalnızca tüm satırlarda %10 KDV ile yapılabilir.")
            continue
        if not price.is_finite() or price < 0 or not rate.is_finite() or rate < 0 or rate > 100:
            problems.append("Geçersiz ürün fiyatı veya KDV.")
            continue
        order = line.order
        if (order.para_birimi or "TRY") != invoice.currency:
            problems.append("Sipariş ve fatura para birimleri farklı; aktarım engellendi.")
        parts = []
        if order.renk:
            parts.append("Renk: " + str(order.renk))
        if order.beden:
            parts.append("Beden: " + str(order.beden))
        items.append({
            "type": "sales_invoice_details",
            "attributes": {
                "quantity": 1,
                "unit_price": str(price),
                "vat_rate": str(rate),
                "description": " / ".join(parts) or "Ürün",
            },
            "relationships": {"product": {"data": {"id": product_id, "type": "products"}}},
        })
    if problems:
        return None, list(dict.fromkeys(problems))
    return {"data": {
        "type": "sales_invoices",
        "attributes": {
            "item_type": "invoice",
            "description": "MoliApp FT-" + str(invoice.pk),
            "issue_date": invoice.invoice_date.isoformat(),
            "due_date": (invoice.due_date or invoice.invoice_date).isoformat(),
            "currency": currency,
            "billing_address": address,
        },
        "relationships": {
            "contact": {"data": {"id": contact.external_contact_id, "type": "contacts"}},
            "details": {"data": items},
        },
    }}, []


def validate_parasut_vat_payload(payload, expected_count):
    """Fail closed before any invoice POST: every transmitted line must have VAT 10."""
    try:
        items = payload["data"]["relationships"]["details"]["data"]
        if len(items) != expected_count or expected_count < 1:
            return False
        return all(Decimal(str(item["attributes"]["vat_rate"])) == Decimal("10") for item in items)
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False
