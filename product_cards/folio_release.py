"""Date guards for actions that release a produced order."""
from django.utils import timezone


def active_release_date(orders):
    """Latest active date among the orders in an outgoing document."""
    return orders.filter(
        invoice_shipment_release_on__gt=timezone.localdate()
    ).order_by("-invoice_shipment_release_on").values_list(
        "invoice_shipment_release_on", flat=True
    ).first()


def order_release_block(order, scheduled_on=None):
    release_on = order.invoice_shipment_release_on
    if release_on and (order.invoice_shipment_locked or (
        scheduled_on is not None and scheduled_on < release_on
    )):
        return release_on
    return None


def release_notice(release_on):
    return f"{release_on:%d.%m.%Y} tarihinden önce faturaya aktarılamaz ve sevk edilemez."
