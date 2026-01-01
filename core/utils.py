import os
from supabase import create_client

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    # ✅ Localde env yoksa patlamasın
    if not url or not key:
        return None

    return create_client(url, key)
