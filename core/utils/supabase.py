from supabase import create_client
from django.conf import settings

def get_supabase():
    if not settings.SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL tanımlı değil")

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY
    )
