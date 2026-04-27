"""Shared Stripe helpers."""
import re
from typing import Any, Dict, Optional

from config import Config


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


def normalize_stripe_checkout_hex_color(value: Optional[str]) -> Optional[str]:
    """
    Stripe Checkout branding colours must be #RRGGBB (6 hex digits).
    Accepts with or without leading #; returns lower-case #rrggbb or None.
    """
    raw = (value or "").strip()
    if not raw:
        return None
    s = raw if raw.startswith("#") else f"#{raw}"
    if len(s) == 4 and s.startswith("#") and len(s[1:]) == 3:
        r, g, b = s[1], s[2], s[3]
        s = f"#{r}{r}{g}{g}{b}{b}"
    if re.match(r"^#[0-9a-fA-F]{6}$", s):
        return s.lower()
    return None


def stripe_checkout_branding_settings_dict() -> Optional[Dict[str, Any]]:
    """
    Optional branding_settings for stripe.checkout.Session.create.
    When any value is set via env, return a dict Stripe accepts; otherwise None (Dashboard defaults only).
    """
    out: Dict[str, Any] = {}
    btn = normalize_stripe_checkout_hex_color(getattr(Config, "STRIPE_CHECKOUT_BRAND_BUTTON_COLOR", None))
    if btn:
        out["button_color"] = btn
    bg = normalize_stripe_checkout_hex_color(getattr(Config, "STRIPE_CHECKOUT_BRAND_BACKGROUND_COLOR", None))
    if bg:
        out["background_color"] = bg
    name = (getattr(Config, "STRIPE_CHECKOUT_BRAND_DISPLAY_NAME", None) or "").strip()
    if name:
        out["display_name"] = name[:500]
    return out if out else None


def merge_stripe_checkout_branding_into_params(create_params: dict) -> None:
    """Mutate create_params in place when branding env vars are set."""
    bs = stripe_checkout_branding_settings_dict()
    if bs:
        create_params["branding_settings"] = bs


def lumo_stripe_subscription_portal_description(business_name: Optional[str]) -> str:
    """
    Text shown on Stripe Customer Portal next to the subscription (subscription.description).
    Stripe documents this field as displayable to the customer in the portal.
    """
    bn = (business_name or "").strip()
    if bn:
        return f"{bn[:400]} — Lumo 22"[:500]
    return "Lumo 22 — 30 Days Captions"
