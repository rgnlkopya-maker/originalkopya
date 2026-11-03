"""Non-database guardrails for backup center compact layout."""
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase


class BackupCenterTemplateTests(SimpleTestCase):
    def test_navigation_buttons_are_removed_but_settings_and_history_remain(self):
        source = (Path(settings.BASE_DIR) / "templates/core/backup_center.html").read_text(encoding="utf-8")
        self.assertNotIn("Föy Yedeklemeye Git", source)
        self.assertNotIn("Çek/Senet Yedeklemeye Git", source)
        self.assertIn("{% url 'backup_policy_update' %}", source)
        self.assertIn("Yedekleme Geçmişi", source)
        self.assertIn('name="frequency"', source)
        self.assertIn('name="hour"', source)
        self.assertIn('name="minute"', source)
        self.assertIn('name="module"', source)
        engines["django"].get_template("core/backup_center.html")
