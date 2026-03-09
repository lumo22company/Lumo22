"""Shared Stripe helpers."""
import re


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
