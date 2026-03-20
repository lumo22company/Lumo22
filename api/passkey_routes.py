"""
WebAuthn passkey registration and authentication for customer accounts.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import uuid
from typing import List, Optional

from flask import Blueprint, jsonify, request, session

from api.auth_routes import get_current_customer
from config import Config
from services.customer_auth_service import CustomerAuthService
from services.login_guard import clear_failures
from services.webauthn_config import get_webauthn_settings
from services.webauthn_credential_service import WebAuthnCredentialService

passkey_bp = Blueprint("passkeys", __name__, url_prefix="/api/auth/passkeys")

_SESSION_REG_CHALLENGE = "passkey_reg_challenge"
_SESSION_AUTH_CHALLENGE = "passkey_auth_challenge"
_SESSION_AUTH_EMAIL = "passkey_auth_email"


def _b64url_to_bytes(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s or "") + pad)


def _store_challenge(key: str, raw: bytes) -> None:
    session[key] = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pop_challenge(key: str) -> Optional[bytes]:
    enc = session.pop(key, None)
    if not enc:
        return None
    try:
        return _b64url_to_bytes(enc)
    except Exception:
        return None


def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()


def _credential_service() -> Optional[WebAuthnCredentialService]:
    try:
        return WebAuthnCredentialService()
    except Exception as e:
        logging.warning("WebAuthnCredentialService unavailable: %s", e)
        return None


@passkey_bp.route("", methods=["GET"])
def list_passkeys():
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    svc = _credential_service()
    if not svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet. Try again later."}), 503
    try:
        rows = svc.list_for_customer(str(customer["id"]))
        return jsonify(
            {
                "ok": True,
                "passkeys": [
                    {
                        "id": str(r.get("id")),
                        "friendly_name": r.get("friendly_name"),
                        "created_at": r.get("created_at"),
                    }
                    for r in rows
                ],
            }
        ), 200
    except Exception as e:
        logging.exception("list_passkeys: %s", e)
        return jsonify({"ok": False, "error": "Could not load passkeys."}), 500


@passkey_bp.route("/<pk_id>", methods=["DELETE"])
def delete_passkey(pk_id: str):
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    svc = _credential_service()
    if not svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet."}), 503
    if svc.delete_for_customer(str(customer["id"]), pk_id):
        return jsonify({"ok": True}), 200
    return jsonify({"ok": False, "error": "Passkey not found or could not be removed."}), 404


@passkey_bp.route("/register/begin", methods=["POST"])
def register_begin():
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    if not customer.get("email_verified", True):
        return jsonify({"ok": False, "error": "Verify your email before adding a passkey."}), 403

    svc = _credential_service()
    if not svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet. Ask support to enable the database table."}), 503

    try:
        from webauthn import generate_registration_options
        from webauthn.helpers.options_to_json import options_to_json
        from webauthn.helpers.structs import AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, UserVerificationRequirement
    except ImportError:
        return jsonify({"ok": False, "error": "Passkeys not enabled on this server."}), 503

    rp_id, rp_name, _origins = get_webauthn_settings()
    challenge = secrets.token_bytes(32)
    _store_challenge(_SESSION_REG_CHALLENGE, challenge)

    exclude: List[PublicKeyCredentialDescriptor] = []
    try:
        for row in svc.list_for_customer(str(customer["id"])):
            cid = row.get("credential_id")
            if cid:
                exclude.append(PublicKeyCredentialDescriptor(id=_b64url_to_bytes(cid)))
    except Exception:
        pass

    user_uuid = uuid.UUID(str(customer["id"]))

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=user_uuid.bytes,
        user_name=(customer.get("email") or "").strip(),
        user_display_name=(customer.get("email") or "Lumo 22 account").strip(),
        challenge=challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude or None,
    )
    return jsonify({"ok": True, "options": json.loads(options_to_json(options))}), 200


@passkey_bp.route("/register/finish", methods=["POST"])
def register_finish():
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    if not customer.get("email_verified", True):
        return jsonify({"ok": False, "error": "Verify your email before adding a passkey."}), 403

    expected_challenge = _pop_challenge(_SESSION_REG_CHALLENGE)
    if not expected_challenge:
        return jsonify({"ok": False, "error": "Registration session expired. Please try again."}), 400

    svc = _credential_service()
    if not svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet."}), 503

    try:
        from webauthn import verify_registration_response
    except ImportError:
        return jsonify({"ok": False, "error": "Passkeys not enabled on this server."}), 503

    rp_id, _rp_name, origins = get_webauthn_settings()
    body = request.get_json(silent=True) or {}
    credential = body.get("credential")
    friendly_name = (body.get("friendly_name") or "").strip()[:80] or None

    if not credential:
        return jsonify({"ok": False, "error": "Missing credential"}), 400

    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origins,
            require_user_verification=True,
        )
    except Exception as e:
        logging.info("passkey register_finish verify failed: %s", e)
        return jsonify({"ok": False, "error": "Could not verify passkey. Please try again."}), 400

    cred_id_b64 = base64.urlsafe_b64encode(verified.credential_id).decode("ascii").rstrip("=")

    transports = None
    try:
        resp = credential.get("response") or {}
        tr = resp.get("transports")
        if isinstance(tr, list):
            transports = [str(x) for x in tr if x]
    except Exception:
        pass

    if not svc.save_credential(
        str(customer["id"]),
        cred_id_b64,
        verified.credential_public_key,
        int(verified.sign_count),
        transports,
        friendly_name,
    ):
        return jsonify({"ok": False, "error": "This passkey may already be registered."}), 409

    return jsonify({"ok": True, "message": "Passkey added."}), 201


@passkey_bp.route("/login/begin", methods=["POST"])
def login_begin():
    try:
        from webauthn import generate_authentication_options
        from webauthn.helpers.options_to_json import options_to_json
        from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
    except ImportError:
        return jsonify({"ok": False, "error": "Passkeys not enabled on this server."}), 503

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Valid email required"}), 400

    auth_svc = CustomerAuthService()
    customer = auth_svc.get_by_email(email)
    if not customer:
        return jsonify({"ok": False, "error": "No account found for that email."}), 404
    if not customer.get("email_verified", True):
        return jsonify({"ok": False, "error": "Please verify your email before signing in."}), 403

    cred_svc = _credential_service()
    if not cred_svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet."}), 503

    rows = cred_svc.list_for_customer(str(customer["id"]))
    if not rows:
        return jsonify({"ok": False, "error": "No passkeys on this account yet. Sign in with password or add a passkey after logging in."}), 400

    allow = []
    for r in rows:
        cid = r.get("credential_id")
        if cid:
            allow.append(PublicKeyCredentialDescriptor(id=_b64url_to_bytes(cid)))

    rp_id, _name, _o = get_webauthn_settings()
    challenge = secrets.token_bytes(32)
    _store_challenge(_SESSION_AUTH_CHALLENGE, challenge)
    session[_SESSION_AUTH_EMAIL] = email

    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return jsonify({"ok": True, "options": json.loads(options_to_json(options))}), 200


@passkey_bp.route("/login/finish", methods=["POST"])
def login_finish():
    try:
        from webauthn import verify_authentication_response
    except ImportError:
        return jsonify({"ok": False, "error": "Passkeys not enabled on this server."}), 503

    expected_challenge = _pop_challenge(_SESSION_AUTH_CHALLENGE)
    email_hint = session.pop(_SESSION_AUTH_EMAIL, None)
    if not expected_challenge:
        return jsonify({"ok": False, "error": "Sign-in session expired. Please try again."}), 400

    body = request.get_json(silent=True) or {}
    credential = body.get("credential")
    if not credential:
        return jsonify({"ok": False, "error": "Missing credential"}), 400

    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        return jsonify({"ok": False, "error": "Invalid credential"}), 400

    cred_id_b64 = str(raw_id).strip()
    cred_svc = _credential_service()
    if not cred_svc:
        return jsonify({"ok": False, "error": "Passkeys are not available yet."}), 503

    row = cred_svc.get_internal_by_credential_id(cred_id_b64)
    if not row:
        return jsonify({"ok": False, "error": "Unknown passkey."}), 400

    if email_hint:
        auth_svc = CustomerAuthService()
        cust = auth_svc.get_by_email(email_hint)
        if not cust or str(cust.get("id")) != str(row.get("customer_id")):
            return jsonify({"ok": False, "error": "Sign-in could not be completed."}), 400

    rp_id, _n, origins = get_webauthn_settings()

    try:
        pub = _b64url_to_bytes(row.get("public_key") or "")
    except Exception:
        return jsonify({"ok": False, "error": "Stored passkey is invalid. Remove it and register again."}), 400

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origins,
            credential_public_key=pub,
            credential_current_sign_count=int(row.get("sign_count") or 0),
            require_user_verification=True,
        )
    except Exception as e:
        logging.info("passkey login_finish verify failed: %s", e)
        return jsonify({"ok": False, "error": "Could not verify passkey. Please try again."}), 400

    auth_svc = CustomerAuthService()
    customer = auth_svc.get_by_id(str(row.get("customer_id")))
    if not customer:
        return jsonify({"ok": False, "error": "Account not found."}), 400

    cred_svc.update_sign_count(str(row.get("id")), int(verified.new_sign_count))

    auth_svc.update_last_login(customer["id"])
    session.permanent = True
    session["customer_id"] = str(customer["id"])
    session["customer_email"] = customer["email"]
    clear_failures((customer.get("email") or "").strip().lower(), _client_ip())

    return jsonify({"ok": True, "email": customer["email"]}), 200
