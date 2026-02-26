"""
Referrer reward: track which invoices we've already applied the 10% discount to (idempotent webhook).
Used when applying referrer discount on invoice.created.
"""
import re
from typing import Optional
from supabase import create_client, Client
from config import Config


def _sanitize_url(u: str) -> str:
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


class ReferralRewardService:
    """Track referral discount redemptions per invoice (avoid double-apply)."""

    def __init__(self):
        if not Config.SUPABASE_URL:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        key = (Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY or "").strip()
        if not key:
            raise ValueError("Supabase configuration missing")
        self.client: Client = create_client(url, key)
        self.table = "referral_discount_redemptions"

    def has_redeemed_for_invoice(self, stripe_invoice_id: str) -> bool:
        """True if we already applied a referrer discount to this invoice (idempotent)."""
        if not stripe_invoice_id or not stripe_invoice_id.strip():
            return True
        result = self.client.table(self.table).select("id").eq(
            "stripe_invoice_id", stripe_invoice_id.strip()
        ).execute()
        return bool(result.data and len(result.data) > 0)

    def record_redemption(self, customer_id: str, stripe_invoice_id: str) -> bool:
        """Record that we applied a referrer discount to this invoice. Returns True on success."""
        if not stripe_invoice_id or not stripe_invoice_id.strip():
            return False
        try:
            self.client.table(self.table).insert({
                "customer_id": str(customer_id),
                "stripe_invoice_id": stripe_invoice_id.strip(),
            }).execute()
            return True
        except Exception:
            return False
