"""Pure Paraşüt sales invoice preparation. No HTTP or e-document functions."""
from decimal import Decimal
from .invoice_models import ParasutCustomerMapping, ParasutProductMapping

CURRENCY = {"TRY": "TRL", "TL": "TRL", "USD": "USD", "EUR": "EUR", "GBP": "GBP"}


def build_parasut_sales_invoice(invoice):
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
        product = ParasutProductMapping.objects.filter(product_code=code).first()
        if not product:
            problems.append("Paraşüt ürün eşleşmesi eksik: " + code[:70])
            continue
        price = Decimal(line.price)
        rate = Decimal(line.vat_rate)
        if not price.is_finite() or price < 0 or not rate.is_finite() or rate < 0 or rate > 100:
            problems.append("Geçersiz ürün fiyatı veya KDV.")
            continue
        items.append({
            "type": "sales_invoice_details",
            "attributes": {
                "quantity": 1,
                "unit_price": str(price),
                "vat_rate": str(rate),
                "description": code,
            },
            "relationships": {"product": {"data": {"id": product.external_product_id, "type": "products"}}},
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
