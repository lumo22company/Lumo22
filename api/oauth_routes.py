"""
Google and Sign in with Apple for customer accounts.
State is signed (itsdangerous) so Apple form_post callbacks work without relying on the session cookie.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import jwt
import requests
from authlib.integrations.flask_client import OAuth
import os

from flask import Blueprint, jsonify, redirect, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.auth_routes import _is_safe_next, clear_failures, set_customer_session
from config import Config
from services.customer_auth_service import CustomerAuthService

oauth_bp = Blueprint("oauth", __name__, url_prefix="/api/auth/oauth")
oauth = OAuth()


@oauth_bp.route("/status", methods=["GET"])
def oauth_status():
    """Debug: whether OAuth env is set (no secrets returned). Open /api/auth/oauth/status on production."""
    return jsonify(
        {
            "google_configured": Config.oauth_google_configured(),
            "apple_configured": Config.oauth_apple_configured(),
            "hint": "Railway needs GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET (exact names). Redeploy after adding.",
        }
    )


def _oauth_state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt="lumo-oauth-v1")


def _sanitize_next(raw: Optional[str]) -> str:
    if not raw or not isinstance(raw, str):
        return "/account"
    s = raw.strip()
    return s if _is_safe_next(s) else "/account"


def pack_oauth_state(next_url: str, referral: str) -> str:
    return _oauth_state_serializer().dumps(
        {"n": _sanitize_next(next_url), "r": (referral or "").strip()[:64]}
    )


def unpack_oauth_state(state_str: str) -> dict:
    if not state_str:
        raise ValueError("missing state")
    return _oauth_state_serializer().loads(state_str, max_age=900)


def init_customer_oauth(app):
    oauth.init_app(app)
    if Config.oauth_google_configured():
        oauth.register(
            name="google",
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=Config.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=Config.GOOGLE_OAUTH_CLIENT_SECRET,
            client_kwargs={"scope": "openid email profile"},
        )


def _apple_client_secret() -> str:
    team = Config.APPLE_OAUTH_TEAM_ID
    cid = Config.APPLE_OAUTH_CLIENT_ID
    kid = Config.APPLE_OAUTH_KEY_ID
    pem = Config.apple_oauth_private_key_pem()
    now = int(time.time())
    payload = {
        "iss": team,
        "iat": now,
        "exp": now + 86400 * 150,
        "aud": "https://appleid.apple.com",
        "sub": cid,
    }
    headers = {"kid": kid, "alg": "ES256"}
    return jwt.encode(payload, pem, algorithm="ES256", headers=headers)


def _decode_apple_id_token(id_token: str) -> dict:
    jwk_client = jwt.PyJWKClient("https://appleid.apple.com/auth/keys")
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)
    return jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=Config.APPLE_OAUTH_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )


def _google_userinfo(token: dict) -> dict:
    ui = token.get("userinfo")
    if isinstance(ui, dict) and ui.get("sub"):
        return ui
    try:
        resp = oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        if resp.ok:
            return resp.json() or {}
    except Exception as e:
        logging.warning("Google userinfo fetch failed: %s", e)
    return {}


def _finish_oauth(
    provider: str,
    subject: str,
    email: Optional[str],
    referral: str,
    next_url: str,
):
    subject = (subject or "").strip()
    if not subject:
        return redirect("/login?oauth_error=profile")

    svc = CustomerAuthService()
    client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

    if provider == "google":
        row = svc.get_by_google_sub(subject)
    else:
        row = svc.get_by_apple_sub(subject)

    if row:
        if not row.get("email_verified", True):
            return redirect("/login?oauth_error=unverified")
        svc.update_last_login(row["id"])
        fresh = svc.get_by_id(str(row["id"])) or row
        set_customer_session(fresh)
        clear_failures(fresh["email"], client_ip)
        return redirect(_sanitize_next(next_url))

    email_l = (email or "").strip().lower()
    if not email_l or "@" not in email_l:
        return redirect("/login?oauth_error=email")

    by_email = svc.get_by_email(email_l)
    if by_email:
        if not by_email.get("email_verified", True):
            return redirect("/login?oauth_error=unverified")
        if provider == "google":
            ok = svc.link_google_sub(str(by_email["id"]), subject)
        else:
            ok = svc.link_apple_sub(str(by_email["id"]), subject)
        if not ok:
            return redirect("/login?oauth_error=link")
        svc.update_last_login(by_email["id"])
        fresh = svc.get_by_id(str(by_email["id"]))
        if not fresh:
            return redirect("/login?oauth_error=link")
        set_customer_session(fresh)
        clear_failures(fresh["email"], client_ip)
        return redirect(_sanitize_next(next_url))

    try:
        new_row = svc.create_oauth(
            email_l,
            google_sub=subject if provider == "google" else None,
            apple_sub=subject if provider == "apple" else None,
            referral_code=(referral or "").strip() or None,
            marketing_opt_in=False,
        )
    except ValueError as e:
        logging.info("OAuth create failed: %s", e)
        el = str(e).lower()
        if "already registered" in el:
            return redirect("/login?oauth_error=registered")
        if "already exists" in el:
            return redirect("/login?oauth_error=exists")
        return redirect("/login?oauth_error=create")

    svc.update_last_login(new_row["id"])
    fresh = svc.get_by_id(str(new_row["id"])) or new_row
    set_customer_session(fresh)
    clear_failures(fresh["email"], client_ip)
    return redirect(_sanitize_next(next_url))


@oauth_bp.route("/google/start")
def google_start():
    if not Config.oauth_google_configured():
        return redirect("/login?oauth_error=disabled")
    next_raw = (request.args.get("next") or "").strip()
    ref = (request.args.get("ref") or "").strip()
    state = pack_oauth_state(next_raw, ref)
    redirect_uri = url_for("oauth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri, state=state, prompt="select_account")


@oauth_bp.route("/google/callback")
def google_callback():
    if not Config.oauth_google_configured():
        return redirect("/login?oauth_error=disabled")
    try:
        state = request.args.get("state", "")
        data = unpack_oauth_state(state)
        token = oauth.google.authorize_access_token()
        prof = _google_userinfo(token)
        sub = (prof.get("sub") or "").strip()
        email = (prof.get("email") or "").strip().lower()
        ev = prof.get("email_verified")
        if ev is False or ev == "false" or ev == 0:
            return redirect("/login?oauth_error=unverified")
        if not sub or not email:
            return redirect("/login?oauth_error=profile")
        return _finish_oauth(
            "google",
            sub,
            email,
            data.get("r") or "",
            data.get("n") or "/account",
        )
    except (BadSignature, SignatureExpired, ValueError):
        return redirect("/login?oauth_error=state")
    except Exception as e:
        logging.exception("Google OAuth: %s", e)
        return redirect("/login?oauth_error=callback")


@oauth_bp.route("/apple/start")
def apple_start():
    if not Config.oauth_apple_configured():
        return redirect("/login?oauth_error=disabled")
    next_raw = (request.args.get("next") or "").strip()
    ref = (request.args.get("ref") or "").strip()
    state = pack_oauth_state(next_raw, ref)
    redirect_uri = url_for("oauth.apple_callback", _external=True)
    qs = {
        "response_type": "code",
        "response_mode": "form_post",
        "client_id": Config.APPLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid email name",
        "state": state,
    }
    from urllib.parse import urlencode

    return redirect("https://appleid.apple.com/auth/authorize?" + urlencode(qs))


@oauth_bp.route("/apple/callback", methods=["POST"])
def apple_callback():
    if not Config.oauth_apple_configured():
        return redirect("/login?oauth_error=disabled")
    err = (request.form.get("error") or "").strip()
    if err:
        return redirect("/login?oauth_error=" + ("denied" if err == "user_cancelled_authorize" else "apple"))

    code = (request.form.get("code") or "").strip()
    state_raw = (request.form.get("state") or "").strip()
    if not code or not state_raw:
        return redirect("/login?oauth_error=apple")

    try:
        data = unpack_oauth_state(state_raw)
    except (BadSignature, SignatureExpired, ValueError):
        return redirect("/login?oauth_error=state")

    redirect_uri = url_for("oauth.apple_callback", _external=True)
    try:
        secret = _apple_client_secret()
    except Exception as e:
        logging.exception("Apple client secret: %s", e)
        return redirect("/login?oauth_error=apple")

    tr = requests.post(
        "https://appleid.apple.com/auth/token",
        data={
            "client_id": Config.APPLE_OAUTH_CLIENT_ID,
            "client_secret": secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=25,
    )
    if not tr.ok:
        logging.warning("Apple token exchange: %s %s", tr.status_code, (tr.text or "")[:300])
        return redirect("/login?oauth_error=token")

    body = tr.json()
    id_token = body.get("id_token")
    if not id_token:
        return redirect("/login?oauth_error=token")

    try:
        claims = _decode_apple_id_token(id_token)
    except Exception as e:
        logging.warning("Apple id_token verify: %s", e)
        return redirect("/login?oauth_error=token")

    sub = (claims.get("sub") or "").strip()
    email = (claims.get("email") or "").strip().lower() or None

    return _finish_oauth(
        "apple",
        sub,
        email,
        data.get("r") or "",
        data.get("n") or "/account",
    )
