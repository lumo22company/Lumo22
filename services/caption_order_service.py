"""
Caption order service: create and update 30 Days Captions orders in Supabase.
Used by Stripe webhook (create) and intake API (update + trigger generation).
"""
import base64
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
        platforms_count: int = 1,
        selected_platforms: Optional[str] = None,
        include_stories: bool = False,
    ) -> Dict[str, Any]:
        """Create order after payment. Returns dict with id, token, customer_email, status.
        platforms_count: number of platforms paid for (1 = base, 2+ = base + add-ons).
        selected_platforms: comma-separated platforms chosen at checkout (e.g. Instagram, LinkedIn).
        include_stories: True when customer paid for 30 Days Story Ideas add-on at checkout."""
        token = _token()
        row = {
            "token": token,
            "customer_email": customer_email,
            "status": "awaiting_intake",
            "stripe_session_id": stripe_session_id,
            "stripe_customer_id": (stripe_customer_id or "").strip() or None,
            "stripe_subscription_id": (stripe_subscription_id or "").strip() or None,
            "platforms_count": max(1, int(platforms_count)),
            "selected_platforms": (selected_platforms or "").strip() or None,
            "include_stories": bool(include_stories),
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

    def set_delivered(
        self, order_id: str, captions_md: str, stories_pdf_bytes: Optional[bytes] = None
    ) -> bool:
        """Mark order delivered; optionally store Stories PDF as base64 for account history."""
        updates = {"status": "delivered", "captions_md": captions_md}
        if stories_pdf_bytes is not None:
            try:
                updates["stories_pdf_base64"] = base64.b64encode(stories_pdf_bytes).decode("ascii")
            except Exception:
                pass
        return self.update(order_id, updates)

    def append_pack_history(self, order_id: str, month_str: str, day_categories: list) -> bool:
        """Append one pack's day categories to pack_history (for subscription variety). day_categories: list of 30 strings."""
        row = self.get_by_id(order_id)
        if not row:
            return False
        history = list(row.get("pack_history") or [])
        if not isinstance(history, list):
            history = []
        entry = {"month": month_str, "day_categories": (day_categories or [])[:30]}
        history.append(entry)
        # Keep last 12 months to avoid unbounded growth
        if len(history) > 12:
            history = history[-12:]
        return self.update(order_id, {"pack_history": history})

    def set_failed(self, order_id: str) -> bool:
        return self.update(order_id, {"status": "failed"})

    def hide_from_history(self, order_id: str) -> bool:
        """Mark order as hidden so it no longer appears in account history (status -> hidden)."""
        return self.update(order_id, {"status": "hidden"})

    def delete_by_customer_email(self, email: str) -> bool:
        """Permanently delete all caption orders for this customer email (for account deletion)."""
        if not email or "@" not in email:
            return False
        try:
            self.client.table(self.table).delete().eq(
                "customer_email", email.strip().lower()
            ).execute()
            return True
        except Exception:
            return False

    def update_customer_email(self, old_email: str, new_email: str) -> bool:
        """Update customer_email on all caption orders for this customer (for email change)."""
        if not old_email or "@" not in old_email or not new_email or "@" not in new_email:
            return False
        try:
            self.client.table(self.table).update({
                "customer_email": new_email.strip().lower(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("customer_email", old_email.strip().lower()).execute()
            return True
        except Exception:
            return False

    def get_active_subscription_orders(self) -> list:
        """Get caption orders that have an active Stripe subscription (for reminder emails)."""
        result = self.client.table(self.table).select(
            "id, token, customer_email, stripe_subscription_id, reminder_sent_period_end, reminder_opt_out"
        ).not_.is_("stripe_subscription_id", "null").execute()
        return result.data or []

    def get_by_stripe_subscription_id(self, stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get order by Stripe subscription id."""
        if not stripe_subscription_id:
            return None
        result = self.client.table(self.table).select("*").eq(
            "stripe_subscription_id", stripe_subscription_id.strip()
        ).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def set_reminder_sent(self, order_id: str, period_end_ts: str) -> bool:
        """Record that we sent a reminder for this billing period."""
        return self.update(order_id, {"reminder_sent_period_end": period_end_ts})
