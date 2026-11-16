from django.apps import AppConfig


class SalesProspectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sales_prospects"
    verbose_name = "Yurt Dışı Müşteri Merkezi"

    def ready(self):
        # Temporary diagnostic gate: never runs in web workers or tests,
        # never writes prospect records, and performs at most five requests.
        import os
        import sys
        if not os.environ.get("MOLI_SEARCH_PROBE") or len(sys.argv) < 2 or sys.argv[1] != "migrate":
            return
        try:
            from .search_probe import CASES, probe_if_requested
            for _ in CASES:
                probe_if_requested()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Optional search probe failed")
