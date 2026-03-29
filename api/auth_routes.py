"""
Auth routes for Lumo 22 customer accounts (DFD, Chat, Captions).
"""
import logging
from flask import Blueprint, request, jsonify, session, redirect, url_for
from config import Config
from services.customer_auth_service import CustomerAuthService
from services.login_guard import check_locked, record_failure, clear_failures
from services.notifications import NotificationService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_COMMON_EMAIL_TYPO_DOMAINS = {
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.con": "gmail.com",
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "outlook.co": "outlook.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "icloud.co": "icloud.com",
    "iclod.com": "icloud.com",
}


def _email_typo_hint(email: str):
    """Return suggested corrected email if domain looks like a common typo."""
    if not email or "@" not in email:
        return None
    parts = email.strip().lower().split("@")
    if len(parts) != 2:
        return None
    local, domain = parts[0].strip(), parts[1].strip()
    if not local or not domain:
        return None
    fixed = _COMMON_EMAIL_TYPO_DOMAINS.get(domain)
    if not fixed:
        return None
    return f"{local}@{fixed}"


def set_customer_session(customer: dict) -> None:
    """Store logged-in customer in Flask session. auth_version invalidates all sessions on password reset."""
    session.permanent = True
    session["customer_id"] = str(customer["id"])
    session["customer_email"] = customer["email"]
    session["auth_version"] = int(customer.get("auth_version") or 0)


def get_current_customer():
    """Get current logged-in customer from session. Clears session if auth_version mismatches DB (password changed elsewhere)."""
    customer_id = session.get("customer_id")
    email = session.get("customer_email")
    if not customer_id or not email:
        return None
    try:
        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if not customer or str(customer.get("id")) != str(customer_id):
            return None
        db_ver = int(customer.get("auth_version") or 0)
        sess_ver = int(session.get("auth_version") or 0)
        if db_ver != sess_ver:
            session.pop("customer_id", None)
            session.pop("customer_email", None)
            session.pop("auth_version", None)
            return None
        return customer
    except Exception:
        pass
    return None


def _base_url():
    """Build base URL for verification links."""
    fallback = "https://www.lumo22.com"
    raw = (Config.BASE_URL or request.url_root or fallback).strip().rstrip("/")
    base = "".join(c for c in raw if ord(c) >= 32 and c not in "\n\r\t")
    if not base:
        base = fallback
    if not base.startswith("http"):
        base = "https://" + base
    return base


def _is_safe_next(next_val):
    """Allow path-only or same-origin URL for redirect after verify (e.g. checkout URL)."""
    if not next_val or not isinstance(next_val, str):
        return False
    next_val = next_val.strip()
    if next_val.startswith("/") and "//" not in next_val[:2]:
        return True
    if next_val.startswith(("http://", "https://")):
        base = (Config.BASE_URL or "").strip() or "https://www.lumo22.com"
        if not base.startswith("http"):
            base = "https://" + base
        return next_val.startswith(base.rstrip("/") + "/") or next_val.startswith(base.rstrip("/"))
    return False


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Create account: email + password. Sends verification email; user must verify before login."""
    try:
        from urllib.parse import quote
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        email_confirm = (data.get("email_confirm") or "").strip().lower()
        password = (data.get("password") or "").strip()
        referral_code = (data.get("referral_code") or data.get("ref") or "").strip() or None
        next_url = (data.get("next") or "").strip() or None

        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400
        if email_confirm and email_confirm != email:
            return jsonify({"ok": False, "error": "Email addresses do not match"}), 400
        typo_hint = _email_typo_hint(email)
        if typo_hint:
            return jsonify({"ok": False, "error": f"Did you mean {typo_hint}?"}), 400
        from services.customer_auth_service import validate_password
        ok, err = validate_password(password)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400

        svc = CustomerAuthService()
        marketing_opt_in = bool(data.get("marketing_opt_in"))
        customer = svc.create(
            email=email,
            password=password,
            referral_code=referral_code,
            marketing_opt_in=marketing_opt_in,
        )

        token = svc.set_email_verification_token(str(customer["id"]))
        if token:
            verify_url = _base_url().rstrip("/") + "/verify-email?token=" + token
            if next_url and _is_safe_next(next_url):
                verify_url += "&next=" + quote(next_url, safe="")
            notif = NotificationService()
            notif.send_welcome_and_verification_email(email, verify_url)

        return jsonify({
            "ok": True,
            "email": customer["email"],
            "message": "Account created. Check your email to verify your address — then you can log in."
        }), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login: email + password. Requires verified email."""
    try:
        data = request.get_json(silent=True) or request.form or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

        if not email or not password:
            return jsonify({"ok": False, "error": "Email and password required"}), 400
        is_locked, retry_after = check_locked(email, client_ip)
        if is_locked:
            return jsonify({
                "ok": False,
                "error": "Too many failed login attempts. Please try again shortly.",
                "retry_after_seconds": retry_after,
            }), 429

        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if not customer:
            record_failure(email, client_ip)
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401
        if not svc.verify_password(customer, password):
            record_failure(email, client_ip)
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401

        # Require email verification (existing customers have email_verified=true from migration)
        if not customer.get("email_verified", True):
            return jsonify({
                "ok": False,
                "error": "Please verify your email before logging in. Check your inbox or request a new link.",
                "needs_verification": True,
            }), 403

        svc.update_last_login(customer["id"])

        session.permanent = True
        session["customer_id"] = str(customer["id"])
        session["customer_email"] = customer["email"]
        clear_failures(email, client_ip)

        return jsonify({"ok": True, "email": customer["email"]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    """Resend email verification link. Body: { "email": "user@example.com" }."""
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400

        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if not customer:
            return jsonify({"ok": True, "message": "If an account exists with that email, you'll receive a verification link shortly."}), 200
        if customer.get("email_verified", True):
            return jsonify({"ok": True, "message": "This account is already verified. You can log in."}), 200

        token = svc.set_email_verification_token(str(customer["id"]))
        if not token:
            return jsonify({"ok": False, "error": "Could not create verification link. Please try again."}), 500

        verify_url = _base_url().rstrip("/") + "/verify-email?token=" + token
        notif = NotificationService()
        sent = notif.send_welcome_and_verification_email(email, verify_url)
        if not sent:
            return jsonify({
                "ok": False,
                "error": "We couldn't send the verification email. Please try again or contact hello@lumo22.com."
            }), 503

        return jsonify({"ok": True, "message": "Verification email sent. Check your inbox (and spam)."}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear session and redirect to home so logout works with or without JS."""
    session.pop("customer_id", None)
    session.pop("customer_email", None)
    session.pop("auth_version", None)
    return redirect("/", code=302)


@auth_bp.route("/delete-account", methods=["POST"])
def delete_account():
    """Permanently delete the current customer account and their caption orders. Requires login."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    customer_id = customer.get("id")
    email = (customer.get("email") or "").strip().lower()
    if not customer_id:
        return jsonify({"ok": False, "error": "Invalid account"}), 400
    try:
        if email:
            from services.caption_order_service import CaptionOrderService
            from services.webauthn_credential_service import WebAuthnCredentialService
            co_svc = CaptionOrderService()
            orders = co_svc.get_by_customer_email_including_stripe_customer(email)
            stripe_customer_ids = list({
                (o.get("stripe_customer_id") or "").strip()
                for o in (orders or [])
                if (o.get("stripe_customer_id") or "").strip()
            })
            for sc_id in stripe_customer_ids:
                try:
                    import stripe
                    if Config.STRIPE_SECRET_KEY:
                        stripe.api_key = Config.STRIPE_SECRET_KEY
                        stripe.Customer.delete(sc_id)
                except Exception as e:
                    if "No such customer" in str(e) or "deleted" in str(e).lower():
                        pass
                    else:
                        logging.warning("Stripe customer delete on account deletion: %s", e)
            try:
                WebAuthnCredentialService().delete_all_for_customer(str(customer_id))
            except Exception as e:
                logging.warning("WebAuthn delete on account deletion: %s", e)
            co_svc.add_to_deleted_blocklist(email)
            co_svc.delete_by_customer_email(email)
        svc = CustomerAuthService()
        if svc.delete_by_id(str(customer_id)):
            session.pop("customer_id", None)
            session.pop("customer_email", None)
            return redirect("/?account_deleted=1", code=302)
        return jsonify({"ok": False, "error": "Could not delete account"}), 500
    except Exception as e:
        logging.exception("delete_account failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/me", methods=["GET"])
def me():
    """Get current customer."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    return jsonify({
        "ok": True,
        "customer": {
            "id": str(customer["id"]),
            "email": customer["email"],
            "created_at": customer.get("created_at"),
            "marketing_opt_in": customer.get("marketing_opt_in", False),
        }
    }), 200


@auth_bp.route("/export-data", methods=["GET"])
def export_data():
    """
    Export all personal data for the logged-in customer (GDPR data portability).
    Returns account info and caption order summaries including intake data.
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid account"}), 400

    from datetime import datetime, timezone
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "id": str(customer.get("id", "")),
            "email": customer.get("email", ""),
            "created_at": customer.get("created_at"),
            "marketing_opt_in": customer.get("marketing_opt_in", False),
        },
        "caption_orders": [],
    }

    try:
        from services.caption_order_service import CaptionOrderService
        co_svc = CaptionOrderService()
        orders = co_svc.get_by_customer_email_including_stripe_customer(email)
        for o in orders or []:
            export["caption_orders"].append({
                "id": str(o.get("id", "")),
                "status": o.get("status"),
                "created_at": o.get("created_at"),
                "platforms_count": o.get("platforms_count"),
                "include_stories": o.get("include_stories"),
                "intake": o.get("intake"),
            })
    except Exception:
        pass

    return jsonify(export), 200


@auth_bp.route("/preferences", methods=["PATCH"])
def update_preferences():
    """Update customer preferences (e.g. marketing_opt_in / unsubscribe)."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    try:
        data = request.get_json() or {}
        opt_in = data.get("marketing_opt_in")
        if opt_in is not None:
            svc = CustomerAuthService()
            if svc.update_marketing_opt_in(str(customer["id"]), bool(opt_in)):
                return jsonify({"ok": True, "marketing_opt_in": bool(opt_in)}), 200
            return jsonify({"ok": False, "error": "Couldn't save preference. Please try again."}), 500
        return jsonify({"ok": False, "error": "No valid preferences to update"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/request-email-change", methods=["POST"])
def request_email_change():
    """Request email change. Sends verification link to the NEW email. Requires login."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    try:
        data = request.get_json() or {}
        new_email = (data.get("new_email") or "").strip().lower()
        if not new_email or "@" not in new_email:
            return jsonify({"ok": False, "error": "Valid new email required"}), 400
        if new_email == (customer.get("email") or "").strip().lower():
            return jsonify({"ok": False, "error": "That's already your email address"}), 400

        svc = CustomerAuthService()
        ok, token = svc.request_email_change(str(customer["id"]), new_email)
        if not ok:
            return jsonify({"ok": False, "error": token or "Could not create verification link"}), 500

        fallback_base = "https://lumo-22-production.up.railway.app"
        raw_base = (Config.BASE_URL or request.url_root or fallback_base).strip().rstrip("/")
        base = "".join(c for c in raw_base if ord(c) >= 32 and c not in "\n\r\t")
        if not base:
            base = fallback_base
        if not base.startswith("http"):
            base = "https://" + base
        confirm_url = base.rstrip("/") + "/change-email-confirm?token=" + str(token)
        confirm_url = "".join(c for c in confirm_url if ord(c) >= 32 and c not in "\n\r\t")
        if not confirm_url or not confirm_url.startswith("http"):
            return jsonify({"ok": False, "error": "Could not generate verification link"}), 500

        notif = NotificationService()
        sent = notif.send_email_change_verification_email(new_email, confirm_url)
        if not sent:
            return jsonify({
                "ok": False,
                "error": "We couldn't send the verification email. Please try again, or contact hello@lumo22.com."
            }), 503

        return jsonify({
            "ok": True,
            "message": f"We've sent a verification link to {new_email}. Click the link in that email to confirm the change."
        }), 200
    except Exception as e:
        logging.exception("request_email_change failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Request password reset. Sends email with reset link if account exists."""
    try:
        data = request.get_json(silent=True) or request.form or {}
        email = (data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400

        # Diagnostic: confirm env so we can see in Railway logs what's in use
        logging.info(
            "[Forgot password] Request for %r | SUPABASE_SERVICE_ROLE_KEY set=%s | SENDGRID set=%s",
            email,
            bool(getattr(Config, "SUPABASE_SERVICE_ROLE_KEY", "")),
            bool(getattr(Config, "SENDGRID_API_KEY", "")),
        )
        svc = CustomerAuthService()
        ok, token = svc.request_password_reset(email)
        if not ok:
            return jsonify({"ok": False, "error": token or "Could not create reset link"}), 500
        if token is None:
            logging.info(
                "[Forgot password] No customer found for %r — no email sent. Check: same Supabase project as DB? SUPABASE_SERVICE_ROLE_KEY set in this service?",
                email,
            )
            return jsonify({"ok": True, "message": "If an account exists with that email, you'll receive a reset link shortly."}), 200

        logging.info("[Forgot password] Customer found for %r, sending reset email", email)
        # Base URL: prefer BASE_URL, then request origin, then fallback so the link is never empty
        fallback_base = "https://lumo-22-production.up.railway.app"
        raw_base = (Config.BASE_URL or request.url_root or fallback_base).strip().rstrip("/")
        base = "".join(c for c in raw_base if ord(c) >= 32 and c not in "\n\r\t")
        if not base:
            base = fallback_base
        if not base.startswith("http"):
            base = "https://" + base
        reset_url = base.rstrip("/") + "/reset-password?token=" + str(token)
        reset_url = "".join(c for c in reset_url if ord(c) >= 32 and c not in "\n\r\t")
        if not reset_url or not reset_url.startswith("http"):
            logging.error("[Forgot password] reset_url invalid or empty, refusing to send")
            return jsonify({"ok": False, "error": "Could not generate reset link. Please try again."}), 500

        logging.info("[Forgot password] Sending reset email to %r | reset_url=%s", email, reset_url[:80])
        notif = NotificationService()
        sent = notif.send_password_reset_email(email, reset_url)
        if not sent:
            logging.warning("[Forgot password] SendGrid failed to send reset email to %r", email)
            return jsonify({
                "ok": False,
                "error": "We couldn't send the reset email right now. Please try again in a few minutes, or contact hello@lumo22.com for help."
            }), 503

        logging.info("[Forgot password] Reset email sent successfully to %r", email)
        return jsonify({"ok": True, "message": "If an account exists with that email, you'll receive a reset link shortly."}), 200
    except Exception as e:
        logging.exception("[Forgot password] Error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/forgot-password/status", methods=["GET"])
def forgot_password_status():
    """Diagnostic: confirm backend has env needed for forgot-password (no secrets). In production, requires ?secret=CRON_SECRET when set."""
    if Config.is_production() and getattr(Config, "CRON_SECRET", None):
        if request.args.get("secret", "").strip() != Config.CRON_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "ok": True,
        "SUPABASE_SERVICE_ROLE_KEY_set": bool(getattr(Config, "SUPABASE_SERVICE_ROLE_KEY", "")),
        "SUPABASE_KEY_set": bool(getattr(Config, "SUPABASE_KEY", "")),
        "SENDGRID_API_KEY_set": bool(getattr(Config, "SENDGRID_API_KEY", "")),
        "FROM_EMAIL": (getattr(Config, "FROM_EMAIL", "") or "not set")[:50],
        "BASE_URL_set": bool(getattr(Config, "BASE_URL", "")),
    }), 200


@auth_bp.route("/change-password", methods=["POST"])
def change_password_logged_in():
    """Change password while logged in: requires current password. Other sessions signed out via auth_version."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    try:
        data = request.get_json() or {}
        current_pw = (data.get("current_password") or "").strip()
        new_pw = (data.get("new_password") or "").strip()
        if not current_pw or not new_pw:
            return jsonify({"ok": False, "error": "Current and new password are required."}), 400
        svc = CustomerAuthService()
        ok, err = svc.change_password_with_current(str(customer["id"]), current_pw, new_pw)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        fresh = svc.get_by_email(customer["email"])
        if fresh:
            set_customer_session(fresh)
        return jsonify({
            "ok": True,
            "message": "Password updated. Other devices were signed out for security.",
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password using token from email."""
    try:
        data = request.get_json() or {}
        token = (data.get("token") or "").strip()
        password = (data.get("password") or "").strip()

        if not token:
            return jsonify({"ok": False, "error": "Reset token required"}), 400

        svc = CustomerAuthService()
        ok, err = svc.reset_password(token, password)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({
            "ok": True,
            "message": "Password updated. You can now log in. For security, other devices were signed out.",
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/create-account", methods=["POST"])
def create_account():
    """
    Create account (e.g. after completing captions intake). Sends verification email;
    user must verify before login — same flow as main signup.
    """
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        email_confirm = (data.get("email_confirm") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400
        if email_confirm and email_confirm != email:
            return jsonify({"ok": False, "error": "Email addresses do not match"}), 400
        typo_hint = _email_typo_hint(email)
        if typo_hint:
            return jsonify({"ok": False, "error": f"Did you mean {typo_hint}?"}), 400
        from services.customer_auth_service import validate_password
        ok, err = validate_password(password)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400

        svc = CustomerAuthService()
        existing = svc.get_by_email(email)
        if existing:
            return jsonify({"ok": False, "error": "An account with this email already exists. Try logging in instead."}), 400

        marketing_opt_in = bool(data.get("marketing_opt_in"))
        customer = svc.create(email=email, password=password, marketing_opt_in=marketing_opt_in)

        token = svc.set_email_verification_token(str(customer["id"]))
        if token:
            verify_url = _base_url().rstrip("/") + "/verify-email?token=" + token
            notif = NotificationService()
            notif.send_welcome_and_verification_email(email, verify_url)

        return jsonify({
            "ok": True,
            "email": customer["email"],
            "message": "Account created. Check your email to verify your address — then you can log in.",
        }), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
