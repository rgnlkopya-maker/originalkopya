"""TCMB selling rates for shipment sales, not invoice or order-day valuation."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

SALE_RATE_FIELDS = {"USD": "usd_try", "EUR": "eur_try", "GBP": "gbp_try"}


def shipment_day(timestamp):
    return timezone.localdate(timestamp) if timezone.is_aware(timestamp) else timestamp.date()


def rates_for_shipment_day(day, cache=None):
    from .models import ExchangeRate

    if cache is not None and day in cache:
        return cache[day]
    rates = dict.fromkeys(SALE_RATE_FIELDS.values())
    rows = ExchangeRate.objects.filter(
        rate_date__range=(day - timedelta(days=7), day),
    ).order_by("-rate_date").values(*rates)
    for row in rows:
        for field, rate in row.items():
            if rates[field] is None and rate is not None and rate > 1:
                rates[field] = rate
        if all(value is not None for value in rates.values()):
            break
    if cache is not None:
        cache[day] = rates
    return rates


def convert_shipment_sale(amount, currency, rates):
    if amount is None:
        return None
    currency = (currency or "TRY").upper()
    field = SALE_RATE_FIELDS.get(currency)
    if currency == "TRY":
        return Decimal(amount)
    rate = rates.get(field)
    if rate is None or rate <= 1:
        return None
    return (Decimal(amount) * rate).quantize(Decimal("0.01"))


def shipment_sale_to_try(snapshot, amount, currency, *, events=None, cache=None):
    """New snapshots retain rates; older ones use their first shipment's archive."""
    if (currency or "TRY").upper() == "TRY":
        return convert_shipment_sale(amount, currency, {})
    if snapshot.fx_reference_date is not None:
        rates = {field: getattr(snapshot, field) for field in SALE_RATE_FIELDS.values()}
    else:
        if events is None:
            first_shipment = snapshot.order.events.filter(
                stage="sevkiyat_durum", value="gonderildi",
            ).order_by("timestamp","id").values_list("timestamp", flat=True).first()
        else:
            first_shipment = next(
                (e.timestamp for e in events if e.stage == "sevkiyat_durum" and e.value == "gonderildi"), None
            )
        day = shipment_day(first_shipment or snapshot.created_at)
        rates = rates_for_shipment_day(day, cache)
    return convert_shipment_sale(amount, currency, rates)
