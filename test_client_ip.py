#!/usr/bin/env python3
"""
Tests for real client IP resolution behind Cloudflare (services/client_ip.py).

The site is Cloudflare-proxied, so a client-supplied X-Forwarded-For is kept and
the real IP is APPENDED after it. Reading the first entry would hand an attacker
control of the value used for per-IP login lockout.
Run with: pytest test_client_ip.py -v
"""
import os

# Minimal env so tests don't require real Supabase/Stripe
os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")

REAL_IP = "203.0.113.7"
SPOOFED_IP = "198.51.100.99"


def _resolve(headers=None, remote_addr="127.0.0.1"):
    """Resolve the client IP inside a request context with the given headers."""
    from app import app
    from services.client_ip import get_client_ip

    with app.test_request_context(
        "/login", headers=headers or {}, environ_base={"REMOTE_ADDR": remote_addr}
    ):
        return get_client_ip()


def test_cf_connecting_ip_is_preferred():
    """Cloudflare sets CF-Connecting-IP and strips any client-supplied copy."""
    assert _resolve({"CF-Connecting-IP": REAL_IP}) == REAL_IP


def test_cf_connecting_ip_wins_over_spoofed_forwarded_for():
    """A forged X-Forwarded-For cannot override the Cloudflare-set header."""
    ip = _resolve({
        "CF-Connecting-IP": REAL_IP,
        "X-Forwarded-For": f"{SPOOFED_IP}, {REAL_IP}",
    })
    assert ip == REAL_IP


def test_spoofed_forwarded_for_resolves_to_appended_real_ip():
    """Without CF-Connecting-IP, use the LAST hop (added by the trusted proxy)."""
    ip = _resolve({"X-Forwarded-For": f"{SPOOFED_IP}, {REAL_IP}"})
    assert ip == REAL_IP
    assert ip != SPOOFED_IP


def test_multiple_spoofed_forwarded_for_entries_resolve_to_real_ip():
    """Padding the header with many forged hops still yields the appended real IP."""
    forged = ", ".join(["10.0.0.1", "192.168.1.1", SPOOFED_IP])
    assert _resolve({"X-Forwarded-For": f"{forged}, {REAL_IP}"}) == REAL_IP


def test_forwarded_for_whitespace_is_trimmed():
    """Odd spacing around hops does not leak into the resolved IP."""
    assert _resolve({"X-Forwarded-For": f"  {SPOOFED_IP} ,   {REAL_IP}   "}) == REAL_IP


def test_no_proxy_headers_falls_back_to_remote_addr():
    """Direct requests (local dev, health checks) fall back to remote_addr."""
    assert _resolve({}, remote_addr=REAL_IP) == REAL_IP


def test_empty_forwarded_for_falls_back_to_remote_addr():
    """A blank X-Forwarded-For must not shadow remote_addr."""
    assert _resolve({"X-Forwarded-For": "  ,  "}, remote_addr=REAL_IP) == REAL_IP


def test_rotating_spoofed_header_does_not_defeat_login_lockout():
    """
    Brute-force guard regression: an attacker rotating X-Forwarded-For per request
    still maps to one real IP, so failures accumulate and lockout triggers.
    """
    from services.login_guard import check_locked, clear_failures, record_failure

    email = "lockout-probe@example.com"
    clear_failures(email, REAL_IP)
    try:
        for attempt in range(5):
            spoofed = f"198.51.100.{attempt}"
            ip = _resolve({"X-Forwarded-For": f"{spoofed}, {REAL_IP}"})
            assert ip == REAL_IP
            record_failure(email, ip)

        is_locked, retry_after = check_locked(email, REAL_IP)
        assert is_locked is True
        assert retry_after > 0
    finally:
        clear_failures(email, REAL_IP)
