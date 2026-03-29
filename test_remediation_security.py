#!/usr/bin/env python3
"""
Tests for remediation security fixes (auth on billing, intake link, export-data, etc.).
Run with: pytest test_remediation_security.py -v
"""
import os
import sys

# Minimal env so tests don't require real Supabase/Stripe
os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")


def test_export_data_requires_auth():
    """Export-data returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.get("/api/auth/export-data")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_intake_link_by_email_requires_auth():
    """Intake link by email returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.get("/api/captions-intake-link-by-email?email=test@example.com")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_change_password_requires_auth():
    """Logged-in change password API returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.post(
            "/api/auth/change-password",
            json={"current_password": "old", "new_password": "newpass123456"},
            content_type="application/json",
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_reduce_subscription_requires_auth():
    """Reduce subscription returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.post(
            "/api/billing/reduce-subscription",
            json={"token": "fake-token", "new_platforms": 1, "new_stories": False},
            content_type="application/json",
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_change_subscription_plan_requires_auth():
    """Change subscription plan returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.post(
            "/api/billing/change-subscription-plan",
            json={"token": "fake-token", "new_platforms": 1, "new_stories": False},
            content_type="application/json",
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_500_template_exists():
    """500 error page template file exists and contains expected text."""
    import pathlib
    path = pathlib.Path(__file__).parent / "templates" / "500.html"
    assert path.exists(), "500.html template should exist"
    content = path.read_text()
    assert "Something went wrong" in content


def test_webhooks_return_200():
    """Typeform/Zapier/generic webhooks return 200 (not 410)."""
    from app import app
    with app.test_client() as c:
        for path in ["/webhooks/typeform", "/webhooks/zapier", "/webhooks/generic"]:
            r = c.post(path, json={}, content_type="application/json")
            assert r.status_code == 200, f"{path} expected 200, got {r.status_code}"


def test_captions_download_uses_date_str():
    """Pack download does not reference undefined pack_start_for_pdf."""
    # Just verify the source code uses date_str, not pack_start_for_pdf
    import api.captions_routes as m
    import inspect
    source = inspect.getsource(m.captions_download)
    assert "pack_start_for_pdf" not in source, "pack_start_for_pdf should be removed"
    assert "date_str" in source, "date_str should be used"


def test_home_and_captions_load():
    """Public pages load without error."""
    from app import app
    with app.test_client() as c:
        assert c.get("/").status_code == 200
        assert c.get("/captions").status_code == 200


def test_session_auth_version_mismatch_clears_session():
    """When DB auth_version != session, user is treated as logged out (password reset elsewhere)."""
    from unittest.mock import patch
    from flask import session
    from app import app
    from api.auth_routes import get_current_customer

    fake_customer = {"id": "abc", "email": "t@example.com", "auth_version": 2}

    with app.test_request_context():
        session["customer_id"] = "abc"
        session["customer_email"] = "t@example.com"
        session["auth_version"] = 1
        with patch("api.auth_routes.CustomerAuthService") as MockSvc:
            MockSvc.return_value.get_by_email.return_value = fake_customer
            assert get_current_customer() is None
            assert session.get("customer_id") is None


def test_apex_host_redirects_to_www():
    """Apex Host (including :port) redirects to www so deep links work when DNS bypasses GoDaddy forwarding."""
    from app import app
    with app.test_client() as c:
        r = c.get("/captions", headers={"Host": "lumo22.com"})
        assert r.status_code == 301
        assert r.headers.get("Location", "").startswith("https://www.lumo22.com/captions")
        r2 = c.get("/captions", headers={"Host": "lumo22.com:443"})
        assert r2.status_code == 301
        assert "www.lumo22.com" in r2.headers.get("Location", "")
        assert c.get("/captions", headers={"Host": "www.lumo22.com"}).status_code == 200


def test_login_required_for_delete_account():
    """Delete account returns 401 when not logged in."""
    from app import app
    with app.test_client() as c:
        r = c.post("/api/auth/delete-account", content_type="application/json")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
