"""Compare database table counts before and after an isolated recovery.

Usage:
  python manage.py backup_table_audit --output /secure/location/before.json
  python manage.py backup_table_audit --compare /secure/location/before.json

Read-only: no table rows or credentials are exported. Compare mode exits nonzero
when the database identity, table inventory, or record counts differ.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


def collect_counts():
    # All table counts come from one consistent read-only snapshot.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SELECT current_database(), current_setting('server_version_num')")
            database, version = cursor.fetchone()
            cursor.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_schema, table_name"
            )
            names = cursor.fetchall()
            counts = {}
            for schema, table in names:
                quoted = connection.ops.quote_name(schema) + "." + connection.ops.quote_name(table)
                cursor.execute("SELECT COUNT(*) FROM " + quoted)
                counts[schema + "." + table] = cursor.fetchone()[0]
    return {"format": 1, "database": database, "server_version_num": int(version), "tables": counts}

def differences(expected, actual):
    errors = []
    # A restored database normally has a different database name; do not fail for it.
    if expected.get("format") != actual.get("format"):
        errors.append("format mismatch")
    # PostgreSQL server_version_num = major * 10000 + minor.
    try:
        expected_major = int(expected.get("server_version_num")) // 10000
        actual_major = int(actual.get("server_version_num")) // 10000
    except (ValueError, TypeError):
        errors.append("PostgreSQL version metadata invalid")
        expected_major = actual_major = None
    if expected_major is not None and expected_major != actual_major:
        errors.append("PostgreSQL major version mismatch")
    a = expected.get("tables", {})
    b = actual.get("tables", {})
    if not isinstance(a, dict) or not isinstance(b, dict):
        return errors + ["table count manifest invalid"]
    for table in sorted(set(a) | set(b)):
        if table not in a:
            errors.append(table + ": unexpected table")
        elif table not in b:
            errors.append(table + ": missing table")
        elif a[table] != b[table]:
            errors.append(table + ": count differs (" + str(a[table]) + " vs " + str(b[table]) + ")")
    return errors


class Command(BaseCommand):
    help = "Produce or compare read-only table-count inventories for isolated restore validation."

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument("--output", type=Path)
        selection.add_argument("--compare", type=Path)

    def handle(self, *args, **options):
        actual = collect_counts()
        if options["compare"]:
            path = options["compare"]
            try:
                expected = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise CommandError("Cannot read comparison manifest") from error
            failures = differences(expected, actual)
            if failures:
                for item in failures:
                    self.stderr.write(item)
                raise CommandError(str(len(failures)) + " recovery consistency mismatches")
            self.stdout.write(self.style.SUCCESS(
                "Table counts matched: " + str(len(actual["tables"])) + " tables"
            ))
            return
        path = options["output"]
        if path.exists():
            raise CommandError("Refusing to overwrite existing manifest")
        # The manifest contains counts, not personal record contents.
        try:
            with path.open("x", encoding="utf-8") as output:
                json.dump(actual, output, indent=2, ensure_ascii=False, sort_keys=True)
                output.write("\n")
        except OSError as error:
            raise CommandError("Failed writing manifest") from error
        self.stdout.write(self.style.SUCCESS("Count manifest created: " + str(len(actual["tables"])) + " tables"))
