"""
In-memory login throttling and temporary lockout.

This is intentionally simple and process-local:
- Track failed attempts per (email, ip)
- Lock the pair for a short cooldown after repeated failures
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, Tuple

_LOCK = Lock()
_WINDOW_MINUTES = 15
_MAX_FAILURES = 5
_LOCKOUT_MINUTES = 15

# key -> {"fails": [datetime, ...], "lock_until": datetime|None}
_STATE: Dict[Tuple[str, str], dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(email: str, ip: str) -> Tuple[str, str]:
    return ((email or "").strip().lower(), (ip or "").strip() or "unknown")


def _prune(entry: dict, now: datetime) -> None:
    cutoff = now - timedelta(minutes=_WINDOW_MINUTES)
    entry["fails"] = [ts for ts in entry.get("fails", []) if ts >= cutoff]
    lock_until = entry.get("lock_until")
    if lock_until and lock_until <= now:
        entry["lock_until"] = None


def check_locked(email: str, ip: str) -> tuple[bool, int]:
    """Return (is_locked, retry_after_seconds)."""
    now = _now()
    with _LOCK:
        entry = _STATE.get(_key(email, ip))
        if not entry:
            return (False, 0)
        _prune(entry, now)
        lock_until = entry.get("lock_until")
        if lock_until and lock_until > now:
            retry_after = int((lock_until - now).total_seconds())
            return (True, max(1, retry_after))
        return (False, 0)


def record_failure(email: str, ip: str) -> int:
    """Record failed login attempt. Returns retry_after_seconds if locked, else 0."""
    now = _now()
    with _LOCK:
        k = _key(email, ip)
        entry = _STATE.setdefault(k, {"fails": [], "lock_until": None})
        _prune(entry, now)
        entry["fails"].append(now)
        if len(entry["fails"]) >= _MAX_FAILURES:
            lock_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            entry["lock_until"] = lock_until
            return max(1, int((lock_until - now).total_seconds()))
        return 0


def clear_failures(email: str, ip: str) -> None:
    """Clear failure state on successful login."""
    with _LOCK:
        _STATE.pop(_key(email, ip), None)
