"""
Rules for captions subscription restart (resubscribe) after a former subscription row.

Used by checkout API, subscription pre-checkout page, and account upgrade hub so behaviour
and copy stay aligned.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional


def is_former_subscription_order_row(o: Optional[dict]) -> bool:
    """
    Order row represents a subscription that has ended (resubscribe path), including when
    subscription_cancelled_at was not set but Stripe sub was cleared on the upgrade row
    (upgraded_from_token set — one-off→sub upgrade then cancel).
    Mirrors app._order_is_former_subscription_row (single source of truth).
    """
    if not o or not isinstance(o, dict):
        return False
    if bool(o.get("subscription_cancelled_at")):
        return True
    pause = o.get("subscription_pause") or {}
    if isinstance(pause, dict) and pause.get("cancelled_now"):
        return True
    if (o.get("stripe_subscription_id") or "").strip():
        return False
    return bool((o.get("upgraded_from_token") or "").strip())


def _parse_order_ts(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if not s:
            return None
        if "T" not in s and len(s) > 10 and s[10] == " ":
            s = s[:10] + "T" + s[11:]
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def order_is_resubscribe_long_gap_after_cancel(o: Optional[dict]) -> bool:
    """
    True when restarting from a former subscription row where cancellation was recorded
    more than 30 days ago. In this case we bill from checkout (no deferred anchor from the
    old pack), do not offer get-pack-now, and copy states the first pack aligns with the
    subscription period starting on checkout day (after intake).
    """
    if not is_former_subscription_order_row(o):
        return False
    cancelled_at = _parse_order_ts(o.get("subscription_cancelled_at"))
    if cancelled_at is None:
        return False
    return datetime.now(timezone.utc) - cancelled_at > timedelta(days=30)
