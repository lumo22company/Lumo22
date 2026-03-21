"""
Shared rules for when a caption order should get another first-pack delivery attempt.
Used by intake resubmit, cron, and APScheduler recovery.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict


def row_needs_first_delivery_retry(
    order: Dict[str, Any],
    *,
    intake_completed_grace_seconds: int = 120,
) -> bool:
    """
    True when no captions pack was stored but we should try generation again.

    intake_completed_grace_seconds: skip very fresh intake_completed rows so we don't
    duplicate-work with the HTTP handler's background thread that just started.
    """
    if (order.get("captions_md") or "").strip():
        return False
    status = (order.get("status") or "").strip()
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
        return True
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
