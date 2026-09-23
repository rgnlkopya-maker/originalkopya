from collections import defaultdict
from django.db import migrations


DRAFT_ID = 71


def repair_podyum_links(apps, schema_editor):
    DraftItem = apps.get_model("product_cards", "ShowroomDraftItem")
    Link = apps.get_model("product_cards", "ShowroomOrderLink")

    items = list(
        DraftItem.objects
        .filter(draft_id=DRAFT_ID)
        .select_related("product_card__urun")
        .order_by("id")
    )
    links = list(
        Link.objects
        .filter(draft_id=DRAFT_ID)
        .select_related("order")
        .order_by("id")
    )

    item_groups = defaultdict(list)
    for item in items:
        key = (
            item.product_card.urun.kod or "",
            item.color or "",
            item.size or "",
        )
        for _ in range(max(1, int(item.quantity or 1))):
            item_groups[key].append(item)

    link_groups = defaultdict(list)
    for link in links:
        if not link.order_id:
            continue
        key = (
            link.order.urun_kodu or "",
            link.order.renk or "",
            link.order.beden or "",
        )
        link_groups[key].append(link)

    for key, group_links in link_groups.items():
        group_items = item_groups.get(key, [])
        if len(group_items) != len(group_links):
            continue
        for link, item in zip(group_links, group_items):
            if link.draft_item_id != item.id:
                link.draft_item_id = item.id
                link.save(update_fields=["draft_item"])


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0030_backfill_showroom_order_links"),
    ]

    operations = [
        migrations.RunPython(repair_podyum_links, migrations.RunPython.noop),
    ]
