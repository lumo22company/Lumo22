"""
Auth routes for Lumo 22 customer accounts (DFD, Chat, Captions).
"""
import logging
from flask import Blueprint, request, jsonify, session, redirect, url_for
from config import Config
from services.customer_auth_service import CustomerAuthService
from services.notifications import NotificationService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def get_current_customer():
    """Get current logged-in customer from session."""
    customer_id = session.get("customer_id")
    email = session.get("customer_email")
    if not customer_id or not email:
        return None
    try:
        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if customer and str(customer.get("id")) == str(customer_id):
            return customer
    except Exception:
        pass
    return None


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Create account: email + password."""
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()
        referral_code = (data.get("referral_code") or data.get("ref") or "").strip() or None

        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400
        if not password or len(password) < 6:
            return jsonify({"ok": False, "error": "Password must be at least 6 characters"}), 400

        svc = CustomerAuthService()
        customer = svc.create(email=email, password=password, referral_code=referral_code)

        session["customer_id"] = str(customer["id"])
        session["customer_email"] = customer["email"]

        return jsonify({"ok": True, "email": customer["email"]}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login: email + password."""
    try:
        data = request.get_json(silent=True) or request.form or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not email or not password:
            return jsonify({"ok": False, "error": "Email and password required"}), 400

        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if not customer:
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401
        if not svc.verify_password(customer, password):
            return jsonify({"ok": False, "error": "Invalid email or password"}), 401

        svc.update_last_login(customer["id"])

        session["customer_id"] = str(customer["id"])
        session["customer_email"] = customer["email"]

        return jsonify({"ok": True, "email": customer["email"]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear session and redirect to home so logout works with or without JS."""
    session.pop("customer_id", None)
    session.pop("customer_email", None)
    return redirect("/", code=302)


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
            "marketing_opt_in": customer.get("marketing_opt_in", True),
        }
    }), 200


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
        return jsonify({"ok": False, "error": "No valid preferences to update"}), 400
    except Exception as e:
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
    """Diagnostic: confirm backend has env needed for forgot-password (no secrets)."""
    return jsonify({
        "ok": True,
        "SUPABASE_SERVICE_ROLE_KEY_set": bool(getattr(Config, "SUPABASE_SERVICE_ROLE_KEY", "")),
        "SUPABASE_KEY_set": bool(getattr(Config, "SUPABASE_KEY", "")),
        "SENDGRID_API_KEY_set": bool(getattr(Config, "SENDGRID_API_KEY", "")),
        "FROM_EMAIL": (getattr(Config, "FROM_EMAIL", "") or "not set")[:50],
        "BASE_URL_set": bool(getattr(Config, "BASE_URL", "")),
    }), 200


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
        return jsonify({"ok": True, "message": "Password updated. You can now log in."}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@auth_bp.route("/create-account", methods=["POST"])
def create_account():
    """
    Create account for existing customer (e.g. after DFD/Captions/Chat setup).
    Used when they set a password after completing a form.
    """
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "Valid email required"}), 400
        if not password or len(password) < 6:
            return jsonify({"ok": False, "error": "Password must be at least 6 characters"}), 400

        svc = CustomerAuthService()
        existing = svc.get_by_email(email)
        if existing:
            return jsonify({"ok": False, "error": "An account with this email already exists. Try logging in instead."}), 400

        customer = svc.create(email=email, password=password)

        session["customer_id"] = str(customer["id"])
        session["customer_email"] = customer["email"]

        return jsonify({"ok": True, "email": customer["email"]}), 201
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
