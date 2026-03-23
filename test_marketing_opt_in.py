"""
Tests for GDPR marketing defaults: signup/create-account pass marketing_opt_in;
/me defaults missing column to False.
"""
import pytest
from unittest.mock import patch

from app import app

VALID_PW = "longpassword123"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@patch("api.auth_routes.NotificationService")
@patch("api.auth_routes.CustomerAuthService")
def test_signup_omits_marketing_defaults_false(mock_svc_cls, _notif, client):
    inst = mock_svc_cls.return_value
    inst.create.return_value = {"id": "id-1", "email": "new@example.com"}
    inst.set_email_verification_token.return_value = "tok"

    r = client.post(
        "/api/auth/signup",
        json={"email": "new@example.com", "password": VALID_PW},
    )
    assert r.status_code == 201
    inst.create.assert_called_once()
    assert inst.create.call_args.kwargs["marketing_opt_in"] is False


@patch("api.auth_routes.NotificationService")
@patch("api.auth_routes.CustomerAuthService")
def test_signup_marketing_true(mock_svc_cls, _notif, client):
    inst = mock_svc_cls.return_value
    inst.create.return_value = {"id": "id-2", "email": "opt@example.com"}
    inst.set_email_verification_token.return_value = "tok"

    r = client.post(
        "/api/auth/signup",
        json={
            "email": "opt@example.com",
            "password": VALID_PW,
            "marketing_opt_in": True,
        },
    )
    assert r.status_code == 201
    assert inst.create.call_args.kwargs["marketing_opt_in"] is True


@patch("api.auth_routes.NotificationService")
@patch("api.auth_routes.CustomerAuthService")
def test_create_account_passes_marketing_false(mock_svc_cls, _notif, client):
    inst = mock_svc_cls.return_value
    inst.get_by_email.return_value = None
    inst.create.return_value = {"id": "id-3", "email": "intake@example.com"}
    inst.set_email_verification_token.return_value = "tok"

    r = client.post(
        "/api/auth/create-account",
        json={"email": "intake@example.com", "password": VALID_PW},
    )
    assert r.status_code == 201
    assert inst.create.call_args.kwargs["marketing_opt_in"] is False


@patch("api.auth_routes.NotificationService")
@patch("api.auth_routes.CustomerAuthService")
def test_create_account_marketing_true(mock_svc_cls, _notif, client):
    inst = mock_svc_cls.return_value
    inst.get_by_email.return_value = None
    inst.create.return_value = {"id": "id-4", "email": "intake2@example.com"}
    inst.set_email_verification_token.return_value = "tok"

    r = client.post(
        "/api/auth/create-account",
        json={
            "email": "intake2@example.com",
            "password": VALID_PW,
            "marketing_opt_in": True,
        },
    )
    assert r.status_code == 201
    assert inst.create.call_args.kwargs["marketing_opt_in"] is True


@patch("api.auth_routes.CustomerAuthService")
def test_me_defaults_marketing_false_when_key_missing(mock_svc_cls, client):
    mock_svc_cls.return_value.get_by_email.return_value = {
        "id": "1",
        "email": "a@b.com",
    }
    with client.session_transaction() as sess:
        sess["customer_id"] = "1"
        sess["customer_email"] = "a@b.com"

    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["customer"]["marketing_opt_in"] is False


@patch("api.auth_routes.CustomerAuthService")
def test_me_reflects_marketing_true(mock_svc_cls, client):
    mock_svc_cls.return_value.get_by_email.return_value = {
        "id": "1",
        "email": "a@b.com",
        "marketing_opt_in": True,
    }
    with client.session_transaction() as sess:
        sess["customer_id"] = "1"
        sess["customer_email"] = "a@b.com"

    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.get_json()["customer"]["marketing_opt_in"] is True
