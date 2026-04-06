"""
Google OAuth for customer accounts (Sign in with Google).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, jsonify, redirect, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.auth_routes import _is_safe_next, clear_failures, set_customer_session
from config import Config
from services.customer_auth_service import CustomerAuthService

oauth_bp = Blueprint("oauth", __name__, url_prefix="/api/auth/oauth")
oauth = OAuth()


@oauth_bp.route("/status", methods=["GET"])
def oauth_status():
    """Debug: whether Google OAuth env is set (no secrets returned)."""
    payload = {
        "google_configured": Config.oauth_google_configured(),
        "hint": "Railway needs GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET (exact names). Redeploy after adding.",
    }
    if Config.oauth_google_configured():
        payload["redirect_uri"] = google_oauth_redirect_uri()
        payload["redirect_uri_hint"] = (
            "Add this exact URL under Google Cloud Console → APIs & Services → Credentials → "
            "your OAuth 2.0 Client → Authorized redirect URIs. Error 400 redirect_uri_mismatch means it is missing or differs (www vs non-www, http vs https)."
        )
    return jsonify(payload)


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


def _canonical_base_url_for_oauth() -> str:
    """Public site URL for OAuth callback. Matches Stripe redirect normalization (apex lumo22.com → www)."""
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    if base in ("https://lumo22.com", "http://lumo22.com"):
        return "https://www.lumo22.com"
    return base


def google_oauth_redirect_uri() -> str:
    """
    Exact redirect_uri sent to Google. Must match an Authorized redirect URI in Google Cloud Console
    character-for-character (scheme, host, path; no trailing slash).
    """
    base = _canonical_base_url_for_oauth()
    if base:
        return f"{base}/api/auth/oauth/google/callback"
    return url_for("oauth.google_callback", _external=True)


def init_customer_oauth(app):
    oauth.init_app(app)
    g_cid = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    g_sec = (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
    if g_cid and g_sec:
        oauth.register(
            name="google",
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_id=g_cid,
            client_secret=g_sec,
            client_kwargs={"scope": "openid email profile"},
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


def _finish_google_oauth(subject: str, email: str, referral: str, next_url: str):
    subject = (subject or "").strip()
    if not subject:
        return redirect("/login?oauth_error=profile")

    svc = CustomerAuthService()
    client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

    row = svc.get_by_google_sub(subject)
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
        if not svc.link_google_sub(str(by_email["id"]), subject):
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
            google_sub=subject,
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
    redirect_uri = google_oauth_redirect_uri()
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
        return _finish_google_oauth(
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
