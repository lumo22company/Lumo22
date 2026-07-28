"""
Reject requests that reach the Railway origin without passing through Cloudflare.

Why this exists
---------------
services/client_ip.py trusts ``CF-Connecting-IP`` because Cloudflare strips any
client-supplied copy. That holds only for traffic that actually went through
Cloudflare. The Railway origin (``*.up.railway.app``) stays publicly reachable,
so an attacker who finds it can talk to the app directly, forge proxy headers
and rotate the IP used by the per-(email, ip) lockout in services/login_guard.py.

How it works
------------
A Cloudflare Transform Rule adds a secret header to every proxied request (see
scripts/setup_cloudflare_security.py --origin-guard). The same secret is set on
the origin as ORIGIN_GUARD_SECRET. Requests arriving without it did not come
through Cloudflare. An IP allowlist of Cloudflare's published ranges is not
usable here: Railway's own proxy sits in front of the app, so the app never sees
Cloudflare's edge IP as remote_addr.

Configuration (all optional — unset means disabled)
---------------------------------------------------
ORIGIN_GUARD_SECRET  Shared secret. Unset → guard is entirely inactive.
ORIGIN_GUARD_MODE    "report" (default) logs what would be blocked without
                     blocking it; "enforce" returns 403.
ORIGIN_GUARD_HEADER  Header name. Default "X-Origin-Auth".

Deploying the code alone changes nothing. Set the secret, watch the logs in
report mode, then switch to enforce.

Machine callers that legitimately hit the origin directly (Stripe webhooks,
SendGrid inbound parse, platform health checks) are exempt — see _EXEMPT_PREFIXES.
Those endpoints authenticate their own callers by signature, and exempting them
does not weaken the goal here, which is protecting the auth surface.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from flask import Response, request

_DEFAULT_HEADER = "X-Origin-Auth"

# Paths that may be called directly at the origin, bypassing Cloudflare.
_EXEMPT_PREFIXES = (
    "/webhooks/",           # Stripe signature-verified; SendGrid inbound parse
    "/.well-known/",        # security.txt, ACME challenges
)


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _secret() -> str:
    return _env("ORIGIN_GUARD_SECRET")


def _header_name() -> str:
    return _env("ORIGIN_GUARD_HEADER") or _DEFAULT_HEADER


def _enforcing() -> bool:
    return _env("ORIGIN_GUARD_MODE").lower() == "enforce"


def is_exempt(path: str) -> bool:
    """True when the path may legitimately be reached without Cloudflare."""
    p = path or "/"
    return any(p.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def came_through_cloudflare(secret: Optional[str] = None) -> bool:
    """True when the current request carries the Cloudflare-injected secret."""
    expected = secret if secret is not None else _secret()
    if not expected:
        return True  # guard not configured; nothing to verify against
    presented = (request.headers.get(_header_name()) or "").strip()
    if not presented:
        return False
    return hmac.compare_digest(presented, expected)


def check_request() -> Optional[Response]:
    """
    before_request hook. Returns a 403 response to short-circuit the request,
    or None to let it proceed.
    """
    if not _secret():
        return None
    if is_exempt(request.path):
        return None
    if came_through_cloudflare():
        return None

    logging.warning(
        "origin_guard: %s request to %s bypassed Cloudflare (remote_addr=%s)",
        "blocked" if _enforcing() else "would block",
        request.path,
        request.remote_addr,
    )
    if not _enforcing():
        return None
    return Response("Direct origin access is not allowed.", status=403)


def init_app(app) -> None:
    """Register the guard. Safe to call unconditionally — inert without a secret."""
    app.before_request(check_request)
