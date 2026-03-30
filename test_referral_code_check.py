"""Referral code check API for captions page Apply button."""
from unittest.mock import patch


def test_referral_code_check_short_invalid():
    from app import app

    with app.test_client() as c:
        r = c.get("/api/referral-code-check?code=ab")
    assert r.status_code == 200
    assert r.get_json() == {"valid": False}


def test_referral_code_check_valid_when_customer_exists():
    from app import app

    fake = {"id": "x", "email": "a@b.com"}
    with app.test_client() as c:
        with patch("services.customer_auth_service.CustomerAuthService.get_by_referral_code", return_value=fake):
            r = c.get("/api/referral-code-check?code=GOODCODE123")
    assert r.status_code == 200
    assert r.get_json() == {"valid": True}


def test_referral_code_check_invalid_when_not_found():
    from app import app

    with app.test_client() as c:
        with patch("services.customer_auth_service.CustomerAuthService.get_by_referral_code", return_value=None):
            r = c.get("/api/referral-code-check?code=NOTFOUND1")
    assert r.status_code == 200
    assert r.get_json() == {"valid": False}
