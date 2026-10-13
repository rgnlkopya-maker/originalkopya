"""Sales-only foreign exchange conversion for showroom orders.

This module intentionally does not read or modify product costs.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SUPPORTED_SALE_CURRENCIES = ("TRY", "USD", "EUR", "GBP")
MONEY_QUANTUM = Decimal("0.01")


def sale_amount_in_try(amount, currency, locked_sale_rate=None):
    """Convert a sale using its own locked rate; never use a cost FX rate."""
    currency = (currency or "TRY").upper()
    if currency not in SUPPORTED_SALE_CURRENCIES:
        raise ValueError("Unsupported sale currency")
    try:
        amount = Decimal(str(amount))
        if not amount.is_finite():
            raise ValueError("Invalid sale amount")
        if currency == "TRY":
            return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        if locked_sale_rate is None:
            raise ValueError("Foreign-currency sales require a locked sale rate")
        rate = Decimal(str(locked_sale_rate))
        if not rate.is_finite() or rate <= 0:
            raise ValueError("Sale rate must be positive")
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid sale amount or rate") from exc
    return (amount * rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
