"""
Initialize Supabase database. For Captions product, ensure caption_orders table exists
(see database_caption_orders.sql or your migration scripts).
"""
import re
from supabase import create_client
from config import Config


def _sanitize_url(u: str) -> str:
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


def init_database():
    """Verify Supabase connection. Table schema is managed via migrations / SQL."""
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("Supabase not configured. Skipping database check.")
        return

    try:
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            print("Supabase URL invalid. Skipping.")
            return
        client = create_client(url, (Config.SUPABASE_KEY or "").strip())

        # Verify caption_orders is accessible (used by Captions product)
        try:
            client.table("caption_orders").select("id").limit(1).execute()
            print("Supabase connected. caption_orders table accessible.")
        except Exception as e:
            print(f"Supabase connected but caption_orders may not exist yet: {e}")
            print("Create it using database_caption_orders.sql or your migration.")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")


if __name__ == "__main__":
    init_database()
