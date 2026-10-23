"""Build BizimHesap AddInvoice JSON locally. This module performs no HTTP writes."""
from decimal import Decimal, ROUND_HALF_UP

CURRENCIES = {"TRY": "TL", "TL": "TL", "USD": "USD", "EUR": "EUR", "GBP": "GBP", "CHF": "CHF"}


def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_invoice_payload(invoice, lines, mapping, firm_id):
    """Return (payload, blockers); never create remote customers, invoices or collections."""
    blockers = []
    if not mapping:
        blockers.append("Cari eşleştirmesi eksik.")
    if not firm_id:
        blockers.append("FirmId tanımlı değil.")
    detail = getattr(invoice.customer, "customer_detail", None)
    address = ((getattr(detail, "fatura_adresi", "") or "").strip()
               or (getattr(detail, "adres", "") or "").strip())
    if not address:
        blockers.append("Müşteri kartında fatura adresi veya adres bilgisi eksik.")
    due_date = invoice.due_date or invoice.invoice_date
    if due_date < invoice.invoice_date:
        blockers.append("Vade tarihi fatura tarihinden önce.")
    currency = CURRENCIES.get(invoice.currency)
    if not currency:
        blockers.append("Para birimi desteklenmiyor.")
    if not lines:
        blockers.append("Fatura satırı yok.")
    if getattr(invoice, "status", "DRAFT") not in ("DRAFT", "FINAL"):
        blockers.append("Fatura durumu aktarım için uygun değil.")
    details = []
    for line in lines:
        price = money(line.price if getattr(line, "order", None) else line.unit_price)
        rate = Decimal(line.vat_rate)
        if not price.is_finite() or price < 0 or not rate.is_finite() or rate < 0 or rate > 100:
            blockers.append("Geçersiz fiyat veya KDV.")
            continue
        order = getattr(line, "order", None)
        if order and (order.para_birimi or "TRY") != invoice.currency:
            blockers.append("Sipariş ve fatura para birimleri farklı; aktarım engellendi.")
        product_name = str(order.urun_kodu if order else line.description or "").strip()
        if not product_name:
            blockers.append("Ürün kodu eksik.")
            continue
        tax = money(price * rate / Decimal("100"))
        details.append({
            "productId": product_name,
            "productName": (" / ".join(str(v) for v in (order.renk, order.beden) if v) or "Ürün") if order else product_name,
            "note": "",
            "taxRate": str(rate),
            "quantity": str(line.quantity) if order is None else 1,
            "unitPrice": str(price),
            "grossPrice": str(money(price * (line.quantity if order is None else 1))),
            "discount": "0.00",
            "net": str(money(price * (line.quantity if order is None else 1))),
            "tax": str(money(tax * (line.quantity if order is None else 1))),
            "total": str(money((price + tax) * (line.quantity if order is None else 1))),
        })
    if any(problem != "FirmId tanımlı değil." for problem in blockers):
        return None, list(dict.fromkeys(blockers))
    net = money(sum((Decimal(x["net"]) for x in details), Decimal("0")))
    tax = money(sum((Decimal(x["tax"]) for x in details), Decimal("0")))
    return {
        "firmId": firm_id,
        "invoiceType": 3,
        **({"invoiceNo": invoice.official_number.strip()} if (invoice.official_number or "").strip() else {}),
        "note": "MoliApp fatura taslağı FT-" + str(invoice.pk),
        "dates": {
            "invoiceDate": invoice.invoice_date.isoformat(),
            "dueDate": due_date.isoformat(),
        },
        "customer": {
            "customerId": mapping.external_customer_id,
            "title": invoice.customer.ad,
            "address": address,
        },
        "details": details,
        "amounts": {
            "currency": currency,
            "gross": str(net),
            "discount": "0.00",
            "net": str(net),
            "tax": str(tax),
            "total": str(money(net + tax)),
        },
    }, list(dict.fromkeys(blockers))
