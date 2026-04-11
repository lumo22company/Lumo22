"""
Shared rules for when a caption order should get another first-pack delivery attempt.
Used by intake resubmit, cron, and APScheduler recovery.

Subscription renewals / Get pack sooner: rows often already have captions_md from a prior month.
Those cases must still be eligible for retry when status is failed or stuck generating.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

# Total failed attempts before auto-retry stops (1st try + 2 automatic retries).
CAPTIONS_MAX_AUTO_DELIVERY_FAILURES = 3


def row_needs_first_delivery_retry(
    order: Dict[str, Any],
    *,
    intake_completed_grace_seconds: int = 120,
) -> bool:
    """
    True when we should try caption generation again (cron / recovery).

    intake_completed_grace_seconds: skip very fresh intake_completed rows so we don't
    duplicate-work with the HTTP handler's background thread that just started.
    """
    status = (order.get("status") or "").strip()
    sub_id = (order.get("stripe_subscription_id") or "").strip()

    # Subscription renewals / Get pack sooner: captions_md may already hold last month's pack.
    # Recovery must not treat "has_md" as "done" for failed or stuck generating rows.
    if sub_id:
        sched = order.get("scheduled_delivery_at")
        if sched:
            try:
                now = datetime.now(timezone.utc)
                if isinstance(sched, str):
                    sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
                else:
                    sched_dt = sched
                if sched_dt.tzinfo is None:
                    sched_dt = sched_dt.replace(tzinfo=timezone.utc)
                if sched_dt > now:
                    return False
            except Exception:
                pass
        if status == "failed":
            n = int(order.get("delivery_failure_count") or 0)
            return n < CAPTIONS_MAX_AUTO_DELIVERY_FAILURES
        if status == "generating":
            updated = order.get("updated_at") or order.get("created_at")
            if not updated:
                return False
            try:
                now = datetime.now(timezone.utc)
                if isinstance(updated, str):
                    udt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                else:
                    udt = updated
                if udt.tzinfo is None:
                    udt = udt.replace(tzinfo=timezone.utc)
                return udt < now - timedelta(minutes=25)
            except Exception:
                return True

    if (order.get("captions_md") or "").strip():
        return False
    sched = order.get("scheduled_delivery_at")
    if sched:
        try:
            now = datetime.now(timezone.utc)
            if isinstance(sched, str):
                sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
            else:
                sched_dt = sched
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=timezone.utc)
            if sched_dt > now:
                return False
        except Exception:
            pass
    if status == "failed":
        n = int(order.get("delivery_failure_count") or 0)
        return n < CAPTIONS_MAX_AUTO_DELIVERY_FAILURES
    if status == "intake_completed":
        updated = order.get("updated_at") or order.get("created_at")
        if updated and intake_completed_grace_seconds > 0:
            try:
                now = datetime.now(timezone.utc)
                if isinstance(updated, str):
                    udt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                else:
                    udt = updated
                if udt.tzinfo is None:
                    udt = udt.replace(tzinfo=timezone.utc)
                if udt > now - timedelta(seconds=intake_completed_grace_seconds):
                    return False
            except Exception:
                pass
        return True
    if status == "generating":
        updated = order.get("updated_at") or order.get("created_at")
        if not updated:
            return False
        try:
            now = datetime.now(timezone.utc)
            if isinstance(updated, str):
                udt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            else:
                udt = updated
            if udt.tzinfo is None:
                udt = udt.replace(tzinfo=timezone.utc)
            return udt < now - timedelta(minutes=25)
        except Exception:
            return False
    return False
