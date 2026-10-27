"""Shared item label for external accounting invoices.

Show only fields before Quantity in the MoliApp invoice, omitting live
production status and joining values with spaces instead of separators.
"""


def external_invoice_item_label(line):
    order = getattr(line, "order", None)
    if order is None:
        return str(getattr(line, "description", "") or "").strip()
    code = str(getattr(order, "urun_kodu", "") or "").strip()
    color = str(getattr(order, "renk", "") or "").strip()
    size = str(getattr(order, "beden", "") or "").strip()
    kind = str(getattr(order, "siparis_tipi", "") or "").strip()
    reference = str(getattr(order, "musteri_referans", "") or "").strip()
    # Only show the special-order marker, matching the MoliApp invoice.
    special = "ÖZEL" if kind.upper() in ("ÖZEL", "OZEL") else ""
    return " ".join(p for p in (code, color, size, special, reference) if p)
