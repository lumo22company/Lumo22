"""Shared Stripe helpers."""
import re
from typing import Optional


def is_valid_stripe_subscription_id(s: str) -> bool:
    """
    Validate Stripe subscription ID before calling API.
    Prevents resource_missing errors from empty/invalid IDs.
    """
    if not s or not isinstance(s, str):
        return False
    s = s.strip()
    # sub_ + 24 alphanumeric chars typical; require min length
    return bool(s.startswith("sub_") and len(s) >= 20 and re.match(r"^sub_[a-zA-Z0-9]+$", s))


def lumo_stripe_subscription_portal_description(business_name: Optional[str]) -> str:
    """
    Text shown on Stripe Customer Portal next to the subscription (subscription.description).
    Stripe documents this field as displayable to the customer in the portal.
    """
    bn = (business_name or "").strip()
    if bn:
        return f"{bn[:400]} — Lumo 22"[:500]
    return "Lumo 22 — 30 Days Captions"
