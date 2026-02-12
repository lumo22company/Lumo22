"""
Caption order service: create and update 30 Days Captions orders in Supabase.
Used by Stripe webhook (create) and intake API (update + trigger generation).
"""
import re
from typing import Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime
import uuid
import secrets
from config import Config


def _token() -> str:
    return secrets.token_urlsafe(16)


def _sanitize_url(u: str) -> str:
    """Remove control chars so httpx/urlparse don't raise InvalidURL (e.g. newline in env)."""
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


class CaptionOrderService:
    """CRUD for caption_orders table."""

    def __init__(self):
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        self.client: Client = create_client(url, (Config.SUPABASE_KEY or "").strip())
        self.table = "caption_orders"

    def create_order(
        self,
        customer_email: str,
        stripe_session_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create order after payment. Returns dict with id, token, customer_email, status."""
        token = _token()
        row = {
            "token": token,
            "customer_email": customer_email,
            "status": "awaiting_intake",
            "stripe_session_id": stripe_session_id,
            "stripe_customer_id": (stripe_customer_id or "").strip() or None,
            "stripe_subscription_id": (stripe_subscription_id or "").strip() or None,
        }
        result = self.client.table(self.table).insert(row).execute()
        if not result.data:
            raise RuntimeError("Failed to create caption order")
        return result.data[0]

    def get_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get order by intake token."""
        result = self.client.table(self.table).select("*").eq("token", token).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by id."""
        result = self.client.table(self.table).select("*").eq("id", order_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_customer_email(self, email: str) -> list:
        """Get all caption orders for a customer email."""
        if not email or "@" not in email:
            return []
        e = email.strip().lower()
        result = self.client.table(self.table).select("*").eq("customer_email", e).order("created_at", desc=True).execute()
        return result.data or []

    def get_by_stripe_session_id(self, stripe_session_id: str) -> Optional[Dict[str, Any]]:
        """Get order by Stripe checkout session id (for thank-you → intake redirect)."""
        if not stripe_session_id:
            return None
        result = self.client.table(self.table).select("*").eq("stripe_session_id", stripe_session_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def update(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """Update order (status, intake, captions_md)."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self.client.table(self.table).update(updates).eq("id", order_id).execute()
        return bool(result.data)

    def save_intake(self, order_id: str, intake: Dict[str, Any]) -> bool:
        """Save intake and set status to intake_completed."""
        return self.update(order_id, {"intake": intake, "status": "intake_completed"})

    def update_intake_only(self, order_id: str, intake: Dict[str, Any]) -> bool:
        """Update intake JSON without changing status or re-triggering generation."""
        return self.update(order_id, {"intake": intake})

    def set_generating(self, order_id: str) -> bool:
        return self.update(order_id, {"status": "generating"})

    def set_delivered(self, order_id: str, captions_md: str) -> bool:
        return self.update(order_id, {"status": "delivered", "captions_md": captions_md})

    def set_failed(self, order_id: str) -> bool:
        return self.update(order_id, {"status": "failed"})
