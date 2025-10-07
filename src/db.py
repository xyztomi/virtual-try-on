from supabase import create_client, Client

from src.config import logger
from src.config import SUPABASE_KEY, SUPABASE_URL


def supabase_create_client() -> Client | None:
    """
    Creates and returns a Supabase client using the configured URL and key.

    Returns:
        Client: Supabase client instance if successful, None otherwise.
    """
    url = SUPABASE_URL
    key = SUPABASE_KEY
    if not url or not key:
        logger.error("SUPABASE_URL or SUPABASE_KEY is not set")
        return None
    try:
        supabase: Client = create_client(url, key)
        logger.info("Supabase client connected successfully!")
        return supabase
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None
