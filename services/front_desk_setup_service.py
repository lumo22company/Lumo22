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
        tone: Optional[str] = None,
        reply_style_examples: Optional[str] = None,
        tight_scheduling_enabled: bool = False,
        minimum_gap_between_appointments: int = 60,
        appointment_duration_minutes: int = 60,
        work_start: Optional[str] = None,
        work_end: Optional[str] = None,
        booking_platform: str = "generic",
        calendly_api_token: Optional[str] = None,
        calendly_event_type_uri: Optional[str] = None,
        vagaro_access_token: Optional[str] = None,
        vagaro_business_id: Optional[str] = None,
        vagaro_service_id: Optional[str] = None,
        auto_reply_enabled: bool = True,
        skip_reply_domains: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a full Front Desk setup. Returns dict with id, done_token, forwarding_email, status."""
        done_token = secrets.token_urlsafe(24)
        short_id = secrets.token_hex(6)
        domain = (Config.INBOUND_EMAIL_DOMAIN or "inbound.lumo22.com").strip().lower()
        forwarding_email = f"reply-{short_id}@{domain}"
        gap = max(15, min(480, minimum_gap_between_appointments))  # clamp 15–480 minutes
        duration = max(15, min(120, appointment_duration_minutes))  # clamp 15–120 minutes
        ws = (work_start or "").strip() or "09:00"
        we = (work_end or "").strip() or "17:00"
        skip_domains = (skip_reply_domains or "").strip() or None
        tone_val = (tone or "").strip() or None
        examples_val = (reply_style_examples or "").strip() or None
        row = {
            "done_token": done_token,
            "customer_email": customer_email,
            "business_name": business_name,
            "enquiry_email": enquiry_email,
            "booking_link": booking_link,
            "tone": tone_val,
            "reply_style_examples": examples_val,
            "forwarding_email": forwarding_email,
            "status": "connected",
            "product_type": "front_desk",
            "chat_enabled": False,
            "tight_scheduling_enabled": tight_scheduling_enabled,
            "minimum_gap_between_appointments": gap,
            "appointment_duration_minutes": duration,
            "work_start": ws,
            "work_end": we,
            "booking_platform": (booking_platform or "generic").strip().lower() or "generic",
            "calendly_api_token": (calendly_api_token or "").strip() or None,
            "calendly_event_type_uri": (calendly_event_type_uri or "").strip() or None,
            "vagaro_access_token": (vagaro_access_token or "").strip() or None,
            "vagaro_business_id": (vagaro_business_id or "").strip() or None,
            "vagaro_service_id": (vagaro_service_id or "").strip() or None,
            "auto_reply_enabled": auto_reply_enabled,
            "skip_reply_domains": skip_domains,
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
        enquiry_types: Optional[list] = None,
        opening_hours: Optional[str] = None,
        reply_same_day: bool = False,
        reply_24h: bool = False,
        tone: Optional[str] = None,
        good_lead_rules: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a chat_only setup with form data and set chat_widget_key, chat_enabled. Returns updated row or None."""
        setup = self.get_by_done_token(done_token)
        if not setup or (setup.get("product_type") or "front_desk") != "chat_only":
            return None
        chat_widget_key = secrets.token_urlsafe(20)
        update_data = {
            "business_name": (business_name or "").strip(),
            "enquiry_email": (enquiry_email or "").strip(),
            "booking_link": (booking_link or "").strip() or None,
            "business_description": (business_description or "").strip() or None,
            "chat_widget_key": chat_widget_key,
            "chat_enabled": True,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if enquiry_types is not None:
            update_data["enquiry_types"] = enquiry_types
        if opening_hours is not None:
            update_data["opening_hours"] = (opening_hours or "").strip() or None
        update_data["reply_same_day"] = bool(reply_same_day)
        update_data["reply_24h"] = bool(reply_24h)
        if tone is not None:
            update_data["tone"] = (tone or "").strip() or None
        if good_lead_rules is not None:
            update_data["good_lead_rules"] = (good_lead_rules or "").strip() or None
        result = self.client.table(self.table).update(update_data).eq("id", setup["id"]).execute()
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

    def get_by_customer_email(self, email: str) -> list:
        """Get all setups (DFD + chat) for a customer email."""
        if not email or "@" not in email:
            return []
        e = email.strip().lower()
        result = self.client.table(self.table).select("*").eq("customer_email", e).order("created_at", desc=True).execute()
        return result.data or []

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

    def set_auto_reply_by_done_token(self, done_token: str, enabled: bool) -> bool:
        """Turn auto-reply on or off for a setup (by secret done_token). Returns True if updated."""
        if not done_token:
            return False
        setup = self.get_by_done_token(done_token)
        if not setup or (setup.get("product_type") or "front_desk") != "front_desk":
            return False
        result = self.client.table(self.table).update({
            "auto_reply_enabled": bool(enabled),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", setup["id"]).execute()
        return bool(result.data)

    def disable_chat_for_customer(self, customer_email: str) -> int:
        """
        Set chat_enabled=False for all setups with this customer_email that have chat.
        Used when DFD/chat subscription is cancelled so the embedded widget stops working.
        Returns number of setups updated.
        """
        if not customer_email or "@" not in customer_email:
            return 0
        setups = self.get_by_customer_email(customer_email)
        count = 0
        for s in setups:
            if s.get("chat_enabled") and s.get("chat_widget_key"):
                result = self.client.table(self.table).update({
                    "chat_enabled": False,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("id", s["id"]).execute()
                if result.data:
                    count += 1
        return count
