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
