"""
Customer auth: Lumo 22 product customers (DFD, Chat, Captions).
Uses Supabase for persistence, Werkzeug for password hashing.
"""
import re
import secrets
from typing import Dict, Any, Optional, Tuple
from supabase import create_client, Client
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config


def _sanitize_url(u: str) -> str:
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


class CustomerAuthService:
    """Auth for Lumo 22 customers (DFD, Chat, Captions)."""

    def __init__(self):
        if not Config.SUPABASE_URL:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        # Prefer service_role key so backend can read/update customers when RLS is enabled (e.g. forgot password)
        key = (Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY or "").strip()
        if not key:
            raise ValueError("Supabase configuration missing (set SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY)")
        self.client: Client = create_client(url, key)
        self.table = "customers"

    def _generate_referral_code(self) -> str:
        """Generate unique 8-char alphanumeric referral code."""
        import string
        chars = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = "".join(secrets.choice(chars) for _ in range(8))
            existing = self.get_by_referral_code(code)
            if not existing:
                return code
        return secrets.token_urlsafe(6).upper().replace("-", "").replace("_", "")[:8]

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get customer by email (case-insensitive)."""
        if not email or "@" not in email:
            return None
        e = email.strip().lower()
        # Try exact match first (all signups store lowercased), then case-insensitive for legacy data
        result = self.client.table(self.table).select("*").eq("email", e).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        result = self.client.table(self.table).select("*").ilike("email", e).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by id."""
        if not customer_id:
            return None
        result = self.client.table(self.table).select("*").eq("id", str(customer_id)).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_referral_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get customer by referral code (case-insensitive)."""
        if not code or len(code) < 4:
            return None
        c = code.strip().upper()
        result = self.client.table(self.table).select("id, email").eq("referral_code", c).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def ensure_referral_code(self, customer_id: str) -> Optional[str]:
        """Ensure customer has a referral code; generate if missing. Returns code or None."""
        result = self.client.table(self.table).select("referral_code").eq("id", customer_id).execute()
        if not result.data or len(result.data) == 0:
            return None
        c = result.data[0]
        code = (c.get("referral_code") or "").strip()
        if code:
            return code
        code = self._generate_referral_code()
        try:
            self.client.table(self.table).update({
                "referral_code": code,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return code
        except Exception:
            return None

    def create(self, email: str, password: str, referral_code: Optional[str] = None) -> Dict[str, Any]:
        """Create customer with hashed password. Raises if email exists."""
        if not email or "@" not in email:
            raise ValueError("Valid email required")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        existing = self.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        referrer_id = None
        if referral_code:
            referrer = self.get_by_referral_code(referral_code)
            if referrer:
                referrer_id = referrer.get("id")
        row = {
            "email": email.strip().lower(),
            "password_hash": pw_hash,
            "referral_code": self._generate_referral_code().upper(),
            "referred_by_customer_id": referrer_id,
        }
        result = self.client.table(self.table).insert(row).execute()
        if not result.data:
            raise RuntimeError("Failed to create customer")
        return result.data[0]

    def verify_password(self, customer: Dict[str, Any], password: str) -> bool:
        """Verify password against stored hash."""
        h = customer.get("password_hash")
        if not h:
            return False
        return check_password_hash(h, password)

    def update_last_login(self, customer_id: str) -> None:
        """Update last_login_at."""
        self.client.table(self.table).update({
            "last_login_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", customer_id).execute()

    def update_marketing_opt_in(self, customer_id: str, opt_in: bool) -> bool:
        """Update marketing_opt_in. Returns True on success."""
        try:
            self.client.table(self.table).update({
                "marketing_opt_in": opt_in,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return True
        except Exception:
            return False

    def increment_referral_discount_credits(self, customer_id: str) -> bool:
        """Add one referral reward credit for the referrer (when a referred friend pays). Returns True on success."""
        try:
            cust = self.get_by_id(customer_id)
            if not cust:
                return False
            current = int(cust.get("referral_discount_credits") or 0)
            self.client.table(self.table).update({
                "referral_discount_credits": current + 1,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return True
        except Exception:
            return False

    def decrement_referral_discount_credits(self, customer_id: str) -> bool:
        """Use one referral credit (when we apply 10% off to referrer's invoice). Returns True on success."""
        try:
            cust = self.get_by_id(customer_id)
            if not cust:
                return False
            current = int(cust.get("referral_discount_credits") or 0)
            if current <= 0:
                return False
            self.client.table(self.table).update({
                "referral_discount_credits": current - 1,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return True
        except Exception:
            return False

    def request_password_reset(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Create password reset token for customer. Returns (success, token_or_error).
        Token is valid for 1 hour. Always returns success=True if email exists (no user enumeration).
        """
        customer = self.get_by_email(email)
        if not customer:
            return (True, None)  # Don't reveal if email exists

        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        try:
            self.client.table(self.table).update({
                "password_reset_token": token,
                "password_reset_expires": expires.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer["id"]).execute()
            return (True, token)
        except Exception as e:
            return (False, str(e))

    def get_by_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get customer by valid reset token. Returns None if expired or invalid."""
        if not token or len(token) < 20:
            return None
        result = self.client.table(self.table).select("*").eq(
            "password_reset_token", token
        ).execute()
        if not result.data or len(result.data) == 0:
            return None
        c = result.data[0]
        expires = c.get("password_reset_expires")
        if expires:
            try:
                exp_str = expires.replace("Z", "")[:19]
                exp_dt = datetime.fromisoformat(exp_str)
                if datetime.utcnow() > exp_dt:
                    return None
            except (TypeError, ValueError):
                return None
        return c

    def reset_password(self, token: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Reset password using token. Returns (success, error_message).
        Clears token on success.
        """
        customer = self.get_by_reset_token(token)
        if not customer:
            return (False, "Invalid or expired reset link. Please request a new one.")

        if not new_password or len(new_password) < 6:
            return (False, "Password must be at least 6 characters")

        try:
            pw_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
            self.client.table(self.table).update({
                "password_hash": pw_hash,
                "password_reset_token": None,
                "password_reset_expires": None,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer["id"]).execute()
            return (True, None)
        except Exception as e:
            return (False, str(e))

    def delete_by_id(self, customer_id: str) -> bool:
        """Permanently delete customer account by id. Returns True on success."""
        if not customer_id:
            return False
        try:
            self.client.table(self.table).delete().eq("id", customer_id).execute()
            return True
        except Exception:
            return False

    def request_email_change(self, customer_id: str, new_email: str) -> Tuple[bool, Optional[str]]:
        """
        Create email change verification token. Returns (success, token_or_error).
        Token is valid for 1 hour. new_email must not already exist.
        """
        if not customer_id or not new_email or "@" not in new_email:
            return (False, "Valid new email required")
        new_email = new_email.strip().lower()
        if self.get_by_email(new_email):
            return (False, "An account with this email already exists")
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=1)
        try:
            self.client.table(self.table).update({
                "email_change_token": token,
                "email_change_new_email": new_email,
                "email_change_expires": expires.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return (True, token)
        except Exception as e:
            return (False, str(e))

    def get_by_email_change_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get customer by valid email change token. Returns None if expired or invalid."""
        if not token or len(token) < 20:
            return None
        result = self.client.table(self.table).select("*").eq(
            "email_change_token", token
        ).execute()
        if not result.data or len(result.data) == 0:
            return None
        c = result.data[0]
        expires = c.get("email_change_expires")
        if expires:
            try:
                exp_str = expires.replace("Z", "")[:19] if isinstance(expires, str) else str(expires)[:19]
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", ""))
                if datetime.utcnow() > exp_dt:
                    return None
            except (TypeError, ValueError):
                return None
        return c

    def confirm_email_change(self, token: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Confirm email change using token. Returns (success, new_email, old_email, error_message).
        Clears token and updates email on success. Caller should update caption_orders and Stripe.
        """
        customer = self.get_by_email_change_token(token)
        if not customer:
            return (False, None, None, "Invalid or expired link. Please request a new one from your account.")

        new_email = (customer.get("email_change_new_email") or "").strip().lower()
        if not new_email or "@" not in new_email:
            return (False, None, None, "Invalid email change request.")
        if self.get_by_email(new_email):
            return (False, None, None, "An account with this email already exists. Please use a different email.")

        old_email = (customer.get("email") or "").strip().lower()
        customer_id = str(customer["id"])

        try:
            self.client.table(self.table).update({
                "email": new_email,
                "email_change_token": None,
                "email_change_new_email": None,
                "email_change_expires": None,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return (True, new_email, old_email, None)
        except Exception as e:
            return (False, None, None, str(e))
