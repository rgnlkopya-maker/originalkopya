from django.conf import settings


def demo_mode(request):
    return {
        "DEMO_MODE": getattr(settings, "DEMO_MODE", False),
        "DEMO_COMPANY_NAME": getattr(settings, "DEMO_COMPANY_NAME", "Moli Demo Atölyesi"),
    }
