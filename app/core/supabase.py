from supabase import create_client, Client
from app.core.config import settings

if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
    raise ValueError("Supabase URL and Anon Key must be set in the .env file")

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)