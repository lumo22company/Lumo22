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
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        self.client: Client = create_client(url, (Config.SUPABASE_KEY or "").strip())
        self.table = "customers"

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get customer by email."""
        if not email or "@" not in email:
            return None
        e = email.strip().lower()
        result = self.client.table(self.table).select("*").eq("email", e).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def create(self, email: str, password: str) -> Dict[str, Any]:
        """Create customer with hashed password. Raises if email exists."""
        if not email or "@" not in email:
            raise ValueError("Valid email required")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        existing = self.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")
        pw_hash = generate_password_hash(password, method="pbkdf2:sha256")
        row = {
            "email": email.strip().lower(),
            "password_hash": pw_hash,
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
