from django.db import migrations


def fix_legacy_showroomfolio_fk(apps, schema_editor):
    """Repair a legacy DB-only FK so deleting a showroom draft cascades safely.

    The legacy product_cards_showroomfolio table is not part of the current
    Django model state, so this migration deliberately inspects PostgreSQL
    metadata and becomes a no-op when that table does not exist.
    """
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    qn = schema_editor.quote_name
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", ["public.product_cards_showroomfolio"])
        if cursor.fetchone()[0] is None:
            return

        cursor.execute(
            """
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_class ref ON ref.oid = con.confrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND nsp.nspname = 'public'
              AND rel.relname = 'product_cards_showroomfolio'
              AND ref.relname = 'product_cards_showroomdraft'
            """
        )
        constraints = cursor.fetchall()

        matching = []
        for name, definition in constraints:
            normalized = " ".join((definition or "").lower().split())
            if "foreign key (draft_id)" not in normalized:
                continue
            if "on delete cascade" in normalized:
                return
            matching.append(name)

        if not matching:
            return

        for name in matching:
            cursor.execute(
                f"ALTER TABLE {qn('product_cards_showroomfolio')} "
                f"DROP CONSTRAINT {qn(name)}"
            )

        cursor.execute(
            f"ALTER TABLE {qn('product_cards_showroomfolio')} "
            f"ADD CONSTRAINT {qn('product_cards_showroomfolio_draft_fk_cascade')} "
            f"FOREIGN KEY ({qn('draft_id')}) "
            f"REFERENCES {qn('product_cards_showroomdraft')} ({qn('id')}) "
            "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("product_cards", "0020_showroompayment"),
    ]

    operations = [
        migrations.RunPython(fix_legacy_showroomfolio_fk, migrations.RunPython.noop),
    ]
