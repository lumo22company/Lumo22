"""
Digital Front Desk setup: store form submissions and support one-click 'Mark as connected'.
Used by /api/front-desk-setup and /api/front-desk-setup-done.
Supports product_type: 'front_desk' (full) or 'chat_only' (Website Chat Widget £59).
"""
import re
import secrets
from typing import Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime
from config import Config


def _sanitize_url(u: str) -> str:
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


class FrontDeskSetupService:
    """CRUD for front_desk_setups table."""

    def __init__(self):
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        self.client: Client = create_client(url, (Config.SUPABASE_KEY or "").strip())
        self.table = "front_desk_setups"

    def create(
        self,
        customer_email: str,
        business_name: str,
        enquiry_email: str,
        booking_link: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a full Front Desk setup. Returns dict with id, done_token, forwarding_email, status."""
        done_token = secrets.token_urlsafe(24)
        short_id = secrets.token_hex(6)
        domain = (Config.INBOUND_EMAIL_DOMAIN or "inbound.lumo22.com").strip().lower()
        forwarding_email = f"reply-{short_id}@{domain}"
        row = {
            "done_token": done_token,
            "customer_email": customer_email,
            "business_name": business_name,
            "enquiry_email": enquiry_email,
            "booking_link": booking_link,
            "forwarding_email": forwarding_email,
            "status": "pending",
            "product_type": "front_desk",
            "chat_enabled": False,
        }
        result = self.client.table(self.table).insert(row).execute()
        if not result.data:
            raise RuntimeError("Failed to create front desk setup")
        return result.data[0]

    def create_chat_only_pending(self, customer_email: str) -> Dict[str, Any]:
        """Create a pending chat-only setup (after £59 payment). Customer completes form to get embed code."""
        done_token = secrets.token_urlsafe(24)
        row = {
            "done_token": done_token,
            "customer_email": customer_email.strip(),
            "business_name": "",
            "enquiry_email": customer_email.strip(),
            "forwarding_email": None,
            "status": "pending",
            "product_type": "chat_only",
            "chat_enabled": False,
        }
        result = self.client.table(self.table).insert(row).execute()
        if not result.data:
            raise RuntimeError("Failed to create chat-only setup")
        return result.data[0]

    def complete_chat_only_setup(
        self,
        done_token: str,
        business_name: str,
        enquiry_email: str,
        booking_link: Optional[str] = None,
        business_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a chat_only setup with form data and set chat_widget_key, chat_enabled. Returns updated row or None."""
        setup = self.get_by_done_token(done_token)
        if not setup or (setup.get("product_type") or "front_desk") != "chat_only":
            return None
        chat_widget_key = secrets.token_urlsafe(20)
        result = self.client.table(self.table).update({
            "business_name": (business_name or "").strip(),
            "enquiry_email": (enquiry_email or "").strip(),
            "booking_link": (booking_link or "").strip() or None,
            "business_description": (business_description or "").strip() or None,
            "chat_widget_key": chat_widget_key,
            "chat_enabled": True,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", setup["id"]).execute()
        if not result.data:
            return None
        out = result.data[0]
        out["chat_widget_key"] = chat_widget_key
        return out

    def get_by_forwarding_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get setup by forwarding_email (for inbound parse webhook)."""
        if not email:
            return None
        to_addr = email.strip().lower()
        result = self.client.table(self.table).select("*").ilike("forwarding_email", to_addr).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        result = self.client.table(self.table).select("*").eq("forwarding_email", to_addr).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_done_token(self, done_token: str) -> Optional[Dict[str, Any]]:
        """Get setup by done_token (for Mark as connected link)."""
        if not done_token:
            return None
        result = self.client.table(self.table).select("*").eq("done_token", done_token).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_chat_widget_key(self, widget_key: str) -> Optional[Dict[str, Any]]:
        """Get setup by chat_widget_key (for /api/chat)."""
        if not widget_key:
            return None
        result = self.client.table(self.table).select("*").eq("chat_widget_key", widget_key).eq("chat_enabled", True).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def mark_connected(self, setup_id: str) -> bool:
        """Set status to connected."""
        result = self.client.table(self.table).update({
            "status": "connected",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", setup_id).execute()
        return bool(result.data)
