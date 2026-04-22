"""
Signed, time-limited token for pre-filling login/signup email from deep links (e.g. one-off upgrade).

Avoids putting raw customer_email in URLs while keeping the same UX. Legacy ?email= is still accepted.
"""
from __future__ import annotations

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from config import Config

_SALT = "lumo-account-email-prefill-v1"
# Long enough for upgrade reminder + slow opens; still bounded.
_MAX_AGE_SEC = 120 * 24 * 3600  # 120 days


def _serializer() -> URLSafeTimedSerializer:
    sk = (getattr(Config, "SECRET_KEY", None) or "").strip() or "dev-secret-key-change-in-production"
    return URLSafeTimedSerializer(sk, salt=_SALT)


def sign_prefill_email(email: str) -> str | None:
    em = (email or "").strip().lower()
    if not em or "@" not in em:
        return None
    try:
        return _serializer().dumps({"e": em})
    except Exception:
        return None


def unsign_prefill_email(token: str) -> str | None:
    t = (token or "").strip()
    if not t:
        return None
    try:
        data = _serializer().loads(t, max_age=_MAX_AGE_SEC)
        if not isinstance(data, dict):
            return None
        em = (data.get("e") or "").strip().lower()
        if em and "@" in em:
            return em
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    return None
