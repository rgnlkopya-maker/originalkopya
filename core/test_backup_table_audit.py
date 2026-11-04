"""Unit tests for the isolated recovery count checker (no database needed)."""
from django.test import SimpleTestCase

from core.management.commands.backup_table_audit import differences


class BackupCountAuditTests(SimpleTestCase):
    def setUp(self):
        self.expected = {
            "format": 1,
            "database": "originalkopya",
            "server_version_num": 180006,
            "tables": {"public.core_order": 40, "public.core_orderevent": 90},
        }

    def test_same_counts_and_major_version_pass(self):
        actual = dict(self.expected, server_version_num=180007)
        self.assertEqual(differences(self.expected, actual), [])

    def test_isolated_database_name_is_allowed(self):
        actual = dict(self.expected, database="moliapp_restore_test")
        self.assertEqual(differences(self.expected, actual), [])

    def test_invalid_version_is_reported(self):
        actual = dict(self.expected, server_version_num="invalid")
        self.assertIn("PostgreSQL version metadata invalid", differences(self.expected, actual))

    def test_count_mismatch_fails(self):
        actual = dict(self.expected, tables={"public.core_order": 39, "public.core_orderevent": 90})
        self.assertTrue(any("core_order" in item for item in differences(self.expected, actual)))

    def test_missing_table_fails(self):
        actual = dict(self.expected, tables={"public.core_order": 40})
        self.assertTrue(any("missing table" in item for item in differences(self.expected, actual)))

    def test_unexpected_table_fails(self):
        actual = dict(self.expected, tables={**self.expected["tables"], "public.other": 1})
        self.assertTrue(any("unexpected table" in item for item in differences(self.expected, actual)))

    def test_major_version_change_fails(self):
        actual = dict(self.expected, server_version_num=190001)
        self.assertIn("PostgreSQL major version mismatch", differences(self.expected, actual))

    def test_collection_uses_repeatable_read_only_snapshot(self):
        from unittest.mock import MagicMock, patch
        from contextlib import nullcontext
        from core.management.commands import backup_table_audit as audit
        fake_cursor = MagicMock()
        fake_cursor.fetchone.side_effect = [
            ("originalkopya", "180006"), (40,), (90,)
        ]
        fake_cursor.fetchall.return_value = [
            ("public", "core_order"), ("public", "core_orderevent")
        ]
        fake_connection = MagicMock()
        fake_connection.cursor.return_value.__enter__.return_value = fake_cursor
        fake_connection.ops.quote_name.side_effect = lambda value: '"' + value + '"'
        with patch.object(audit, "connection", fake_connection), patch.object(
            audit.transaction, "atomic", return_value=nullcontext()
        ):
            result = audit.collect_counts()
        self.assertEqual(result["tables"], self.expected["tables"])
        statements = [args.args[0] for args in fake_cursor.execute.call_args_list]
        self.assertEqual(statements[0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertEqual(statements[1], "SELECT current_database(), current_setting('server_version_num')")
        self.assertTrue(all(statement.startswith("SELECT ") for statement in statements[1:]))

    def test_non_dictionary_manifest_is_rejected(self):
        actual = dict(self.expected, tables=[])
        self.assertIn("table count manifest invalid", differences(self.expected, actual))

    def test_missing_table_counts_are_rejected(self):
        actual = dict(self.expected)
        del actual["tables"]
        self.assertIn("table count manifest invalid", differences(self.expected, actual))

    def test_empty_table_counts_are_rejected(self):
        actual = dict(self.expected, tables={})
        self.assertIn("table count manifest invalid", differences(self.expected, actual))

    def test_invalid_row_counts_are_rejected(self):
        actual = dict(self.expected, tables={"public.core_order": -1})
        self.assertIn("restored row count invalid", differences(self.expected, actual))

    def test_boolean_row_counts_are_rejected(self):
        actual = dict(self.expected, tables={"public.core_order": True})
        self.assertIn("restored row count invalid", differences(self.expected, actual))

    def test_missing_format_is_rejected(self):
        actual = dict(self.expected)
        del actual["format"]
        self.assertIn("format mismatch", differences(self.expected, actual))

    def test_missing_version_is_rejected(self):
        actual = dict(self.expected)
        del actual["server_version_num"]
        self.assertIn("PostgreSQL version metadata invalid", differences(self.expected, actual))

    def test_non_mapping_manifest_is_rejected(self):
        self.assertEqual(differences(self.expected, []), ["manifest invalid"])
