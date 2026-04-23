"""Referral code check API for captions page Apply button."""
from unittest.mock import MagicMock, patch


def test_referral_code_check_short_invalid():
    from app import app

    with app.test_client() as c:
        r = c.get("/api/referral-code-check?code=ab")
    assert r.status_code == 200
    assert r.get_json() == {"valid": False}


def test_referral_code_check_valid_when_customer_exists():
    from app import app

    fake = {"id": "x", "email": "a@b.com"}
    # Avoid real Supabase in CustomerAuthService.__init__ (CI uses a placeholder key that fails create_client).
    mock_svc = MagicMock()
    mock_svc.get_by_referral_code.return_value = fake
    with app.test_client() as c:
        with patch("services.customer_auth_service.CustomerAuthService", return_value=mock_svc):
            r = c.get("/api/referral-code-check?code=GOODCODE123")
    assert r.status_code == 200
    assert r.get_json() == {"valid": True}


def test_referral_code_check_invalid_when_not_found():
    from app import app

    mock_svc = MagicMock()
    mock_svc.get_by_referral_code.return_value = None
    with app.test_client() as c:
        with patch("services.customer_auth_service.CustomerAuthService", return_value=mock_svc):
            r = c.get("/api/referral-code-check?code=NOTFOUND1")
    assert r.status_code == 200
    assert r.get_json() == {"valid": False}
