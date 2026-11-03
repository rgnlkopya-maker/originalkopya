"""Legacy compatibility entrypoint for order update notification publishing.

Ordinary order field edits must not create inbox records or browser Push.
Their audit history is written separately as OrderEvent by the edit view.
"""


def publish_order_update(*, order, changed_fields, actor):
    """Intentionally disabled: no notification for routine order edits."""
    return 0
