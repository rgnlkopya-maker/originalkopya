from collections import defaultdict
from zoneinfo import ZoneInfo

from django.db import migrations


ISTANBUL = ZoneInfo("Europe/Istanbul")


def backfill_links(apps, schema_editor):
    ShowroomDraft = apps.get_model("product_cards", "ShowroomDraft")
    ShowroomOrderLink = apps.get_model("product_cards", "ShowroomOrderLink")
    Order = apps.get_model("core", "Order")

    linked_order_ids = set(
        ShowroomOrderLink.objects.exclude(order_id=None).values_list("order_id", flat=True)
    )

    drafts = (
        ShowroomDraft.objects
        .filter(status="TRANSFERRED", orders_created=True)
        .prefetch_related("items__product_card__urun")
        .order_by("id")
    )

    for draft in drafts:
        if not draft.customer_id or not draft.updated_at:
            continue

        local_date = draft.updated_at.astimezone(ISTANBUL).date()
        groups = defaultdict(list)

        for item in draft.items.all().order_by("id"):
            code = item.product_card.urun.kod
            key = (
                code,
                item.color or "",
                item.size or "",
            )
            groups[key].append(item)

        for (code, color, size), items in groups.items():
            needed = sum(max(1, int(item.quantity or 1)) for item in items)

            orders = list(
                Order.objects.filter(
                    musteri_id=draft.customer_id,
                    siparis_tipi=draft.order_type,
                    urun_kodu=code,
                    renk=color or None,
                    beden=size or None,
                    siparis_tarihi=local_date,
                )
                .exclude(id__in=linked_order_ids)
                .order_by("id")
            )

            # Yanlış siparişi bağlamamak için yalnızca birebir adet eşleşmesinde ilerle.
            if len(orders) != needed:
                continue

            pos = 0
            for item in items:
                qty = max(1, int(item.quantity or 1))
                for _ in range(qty):
                    order = orders[pos]
                    pos += 1
                    ShowroomOrderLink.objects.create(
                        draft_id=draft.id,
                        draft_item_id=item.id,
                        order_id=order.id,
                        order_number=order.siparis_numarasi or "",
                    )
                    linked_order_ids.add(order.id)


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0029_showroomorderlink_preserve_deleted"),
    ]

    operations = [
        migrations.RunPython(backfill_links, migrations.RunPython.noop),
    ]
