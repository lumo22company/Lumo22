"""
Resolve the real client IP behind Cloudflare.

The site is served through Cloudflare (apex and www are proxied — see
scripts/setup_cloudflare_security.py), so request headers must be read with the
proxy chain in mind:

- ``CF-Connecting-IP`` is set by Cloudflare and any client-supplied value is
  stripped, so it is the trustworthy source when present.
- ``X-Forwarded-For`` is *appended to* by each proxy. A client can send its own
  header and Cloudflare will append the real IP after it, so the LAST entry
  (added by the nearest trusted proxy) is the one to use — never the first,
  which is fully attacker-controlled.
- ``remote_addr`` is the fallback for direct/local requests with no proxy.

Using the spoofable first entry would let an attacker rotate the header per
request and dodge the per-(email, ip) lockout in services/login_guard.py.
"""
from __future__ import annotations

from flask import request


def get_client_ip() -> str:
    """Return the best-effort real client IP for the current request."""
    cf_ip = (request.headers.get("CF-Connecting-IP") or "").strip()
    if cf_ip:
        return cf_ip

    forwarded = request.headers.get("X-Forwarded-For") or ""
    hops = [part.strip() for part in forwarded.split(",") if part.strip()]
    if hops:
        return hops[-1]

    return (request.remote_addr or "").strip()
