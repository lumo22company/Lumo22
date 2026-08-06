#!/usr/bin/env python3
"""
Tests for the Cloudflare origin guard (services/origin_guard.py).

The Railway origin stays publicly reachable, so a request that skips Cloudflare
can forge proxy headers and defeat the per-IP login lockout. The guard rejects
those, but only once ORIGIN_GUARD_SECRET is set and the mode is "enforce".
Run with: pytest test_origin_guard.py -v
"""
import os

import pytest

# Minimal env so tests don't require real Supabase/Stripe
os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")

SECRET = "test-origin-secret-abc123"


@pytest.fixture
def guard_env(monkeypatch):
    """Configure the guard; each test opts into a mode."""
    def _configure(mode="enforce", secret=SECRET, header=None):
        monkeypatch.setenv("ORIGIN_GUARD_MODE", mode)
        if secret is None:
            monkeypatch.delenv("ORIGIN_GUARD_SECRET", raising=False)
        else:
            monkeypatch.setenv("ORIGIN_GUARD_SECRET", secret)
        if header is None:
            monkeypatch.delenv("ORIGIN_GUARD_HEADER", raising=False)
        else:
            monkeypatch.setenv("ORIGIN_GUARD_HEADER", header)
    return _configure


def _get(path="/login", headers=None):
    from app import app
    with app.test_client() as c:
        return c.get(path, headers=headers or {})


def test_disabled_by_default(monkeypatch):
    """No ORIGIN_GUARD_SECRET → guard is inert and the site behaves normally."""
    monkeypatch.delenv("ORIGIN_GUARD_SECRET", raising=False)
    monkeypatch.delenv("ORIGIN_GUARD_MODE", raising=False)
    assert _get("/login").status_code == 200


def test_enforce_blocks_request_without_secret_header(guard_env):
    """A direct hit to the origin carries no Cloudflare-stamped header → 403."""
    guard_env(mode="enforce")
    assert _get("/login").status_code == 403


def test_enforce_allows_request_with_correct_secret(guard_env):
    """Traffic through Cloudflare carries the stamped header → passes through."""
    guard_env(mode="enforce")
    assert _get("/login", {"X-Origin-Auth": SECRET}).status_code == 200


def test_enforce_rejects_wrong_secret(guard_env):
    """A guessed or stale header value is not accepted."""
    guard_env(mode="enforce")
    assert _get("/login", {"X-Origin-Auth": "wrong-value"}).status_code == 403


def test_report_mode_does_not_block(guard_env):
    """Report mode logs but lets traffic through, so it is safe to roll out first."""
    guard_env(mode="report")
    assert _get("/login").status_code == 200


def test_mode_defaults_to_report(guard_env, monkeypatch):
    """An unset mode must not block — enforcing requires an explicit opt-in."""
    guard_env(mode="enforce")
    monkeypatch.delenv("ORIGIN_GUARD_MODE", raising=False)
    assert _get("/login").status_code == 200


def test_webhook_paths_stay_exempt_under_enforce(guard_env):
    """
    Stripe and SendGrid may call the origin directly; blocking them would break
    payments and inbound email. They authenticate by signature instead.
    """
    from app import app

    guard_env(mode="enforce")
    with app.test_client() as c:
        r = c.get("/webhooks/stripe")
    assert r.status_code != 403


def test_well_known_stays_exempt_under_enforce(guard_env):
    """security.txt must remain fetchable for disclosure/scanning."""
    guard_env(mode="enforce")
    assert _get("/.well-known/security.txt").status_code == 200


def test_custom_header_name_is_honoured(guard_env):
    """ORIGIN_GUARD_HEADER lets the stamped header be renamed."""
    guard_env(mode="enforce", header="X-Lumo-Edge")
    assert _get("/login", {"X-Lumo-Edge": SECRET}).status_code == 200
    assert _get("/login", {"X-Origin-Auth": SECRET}).status_code == 403


def test_forged_forwarded_for_cannot_reach_login_when_enforcing(guard_env):
    """
    The point of the guard: the direct-origin path that would let an attacker
    rotate X-Forwarded-For never reaches the login handler.
    """
    guard_env(mode="enforce")
    from app import app
    with app.test_client() as c:
        r = c.post(
            "/login",
            data={"email": "victim@example.com", "password": "guess"},
            headers={"X-Forwarded-For": "198.51.100.42"},
        )
    assert r.status_code == 403
