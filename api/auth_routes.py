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
        data = request.get_json() or {}
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
    """Logout."""
    session.pop("customer_id", None)
    session.pop("customer_email", None)
    return jsonify({"ok": True}), 200


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

        svc = CustomerAuthService()
        ok, token = svc.request_password_reset(email)
        if not ok:
            return jsonify({"ok": False, "error": token or "Could not create reset link"}), 500
        if token is None:
            logging.info(
                f"[Forgot password] No customer found for {email!r} — no email sent. "
                "If the email is in the DB, set SUPABASE_SERVICE_ROLE_KEY in Railway (not just anon key) so RLS does not block the backend."
            )
            return jsonify({"ok": True, "message": "If an account exists with that email, you'll receive a reset link shortly."}), 200

        base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
        if base and not base.startswith("http"):
            base = "https://" + base
        reset_url = f"{base}/reset-password?token={token}" if base else None
        if not reset_url:
            return jsonify({"ok": False, "error": "BASE_URL not configured"}), 500

        subject = "Reset your Lumo 22 password"
        body = f"""Hi,

You requested a password reset for your Lumo 22 account.

Click the link below to set a new password (link expires in 1 hour):

{reset_url}

If you didn't request this, you can ignore this email. Your password will stay the same.

— Lumo 22
"""
        logging.info(f"[Forgot password] Sending reset email to {email!r} from {getattr(Config, 'FROM_EMAIL', '')!r}")
        notif = NotificationService()
        sent = notif.send_email(email, subject, body)
        if not sent:
            logging.warning(f"[Forgot password] SendGrid failed to send reset email to {email}")
            return jsonify({
                "ok": False,
                "error": "We couldn't send the reset email right now. Please try again in a few minutes, or contact hello@lumo22.com for help."
            }), 503

        return jsonify({"ok": True, "message": "If an account exists with that email, you'll receive a reset link shortly."}), 200
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
