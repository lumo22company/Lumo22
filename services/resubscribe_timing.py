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
    True when restarting from a former subscription row where the end of the prior
    subscription lies more than 30 days in the past. In this case we bill from checkout
    (no deferred anchor from the old pack), do not offer get-pack-now, and copy states the
    first pack aligns with the subscription period starting on checkout day (after intake).

    Detection order:
    1. subscription_cancelled_at in the database (preferred).
    2. subscription_pause.stripe_cancel_unix from Stripe subscription payload (account load
       or any code path that attached _pause_info_from_subscription).
    3. Fallback: no active stripe_subscription_id on the row, the pack was delivered at least
       once, and updated_at is more than 30 days ago (covers missing cancellation column when
       the row has not been touched recently — e.g. webhook gap).
    """
    if not is_former_subscription_order_row(o):
        return False
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=30)

    cancelled_at = _parse_order_ts(o.get("subscription_cancelled_at"))
    if cancelled_at is not None:
        return now - cancelled_at > threshold

    pause = o.get("subscription_pause") or {}
    if isinstance(pause, dict):
        ts = pause.get("stripe_cancel_unix")
        if ts is not None:
            try:
                dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                return now - dt > threshold
            except (TypeError, ValueError, OSError):
                pass

    if (o.get("stripe_subscription_id") or "").strip():
        return False
    delivered = bool((o.get("delivered_at") or "").strip()) or str(o.get("status") or "").strip().lower() == "delivered"
    if not delivered:
        return False
    row_updated = _parse_order_ts(o.get("updated_at"))
    if row_updated is None:
        return False
    return now - row_updated > threshold
