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


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """Check password: at least 12 characters, at least 1 number. Returns (ok, error_message)."""
    if not password or len(password) < 12:
        return (False, "Password must be at least 12 characters")
    if not any(c.isdigit() for c in password):
        return (False, "Password must include at least one number")
    return (True, None)


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

    def get_by_google_sub(self, google_sub: str) -> Optional[Dict[str, Any]]:
        if not (google_sub or "").strip():
            return None
        result = self.client.table(self.table).select("*").eq("google_sub", google_sub.strip()).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_apple_sub(self, apple_sub: str) -> Optional[Dict[str, Any]]:
        if not (apple_sub or "").strip():
            return None
        result = self.client.table(self.table).select("*").eq("apple_sub", apple_sub.strip()).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def _google_sub_taken_by_other(self, google_sub: str, exclude_customer_id: str) -> bool:
        row = self.get_by_google_sub(google_sub)
        return bool(row and str(row.get("id")) != str(exclude_customer_id))

    def _apple_sub_taken_by_other(self, apple_sub: str, exclude_customer_id: str) -> bool:
        row = self.get_by_apple_sub(apple_sub)
        return bool(row and str(row.get("id")) != str(exclude_customer_id))

    def link_google_sub(self, customer_id: str, google_sub: str) -> bool:
        """Attach Google subject to an existing row. Fails if sub already linked elsewhere."""
        if not customer_id or not (google_sub or "").strip():
            return False
        if self._google_sub_taken_by_other(google_sub, customer_id):
            return False
        try:
            self.client.table(self.table).update({
                "google_sub": google_sub.strip(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", str(customer_id)).execute()
            return True
        except Exception:
            return False

    def link_apple_sub(self, customer_id: str, apple_sub: str) -> bool:
        if not customer_id or not (apple_sub or "").strip():
            return False
        if self._apple_sub_taken_by_other(apple_sub, customer_id):
            return False
        try:
            self.client.table(self.table).update({
                "apple_sub": apple_sub.strip(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", str(customer_id)).execute()
            return True
        except Exception:
            return False

    def create_oauth(
        self,
        email: str,
        *,
        google_sub: Optional[str] = None,
        apple_sub: Optional[str] = None,
        referral_code: Optional[str] = None,
        marketing_opt_in: bool = False,
    ) -> Dict[str, Any]:
        """
        New account from Google or Apple (verified email from IdP).
        password_hash is omitted (NULL). Exactly one of google_sub / apple_sub must be set.
        """
        if not email or "@" not in email:
            raise ValueError("Valid email required")
        gs = (google_sub or "").strip()
        ap = (apple_sub or "").strip()
        if bool(gs) == bool(ap):
            raise ValueError("OAuth provider subject required")
        if gs and self.get_by_google_sub(gs):
            raise ValueError("This Google account is already registered")
        if ap and self.get_by_apple_sub(ap):
            raise ValueError("This Apple account is already registered")
        existing = self.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")
        referrer_id = None
        if referral_code:
            referrer = self.get_by_referral_code(referral_code)
            if referrer:
                referrer_id = referrer.get("id")
        row: Dict[str, Any] = {
            "email": email.strip().lower(),
            "password_hash": None,
            "email_verified": True,
            "referral_code": self._generate_referral_code().upper(),
            "referred_by_customer_id": referrer_id,
            "marketing_opt_in": bool(marketing_opt_in),
        }
        if gs:
            row["google_sub"] = gs
        if ap:
            row["apple_sub"] = ap
        result = self.client.table(self.table).insert(row).execute()
        if not result.data:
            raise RuntimeError("Failed to create customer")
        return result.data[0]

    def ensure_referral_code(
        self, customer_id: str, *, stripe_promotion_sync: bool = True
    ) -> Tuple[Optional[str], bool]:
        """Ensure customer has a referral code; generate if missing.
        Returns (code_or_None, need_refresh_customer_row). Second is True when DB/Stripe may have updated the row.
        When stripe_promotion_sync is False (e.g. non-refer account sections), skip creating the Stripe Promotion Code
        so /account loads do not pay that API cost; sync on /account/refer or /api/account/referral-stripe-sync."""
        result = (
            self.client.table(self.table)
            .select("referral_code, stripe_referral_promotion_code_id")
            .eq("id", customer_id)
            .execute()
        )
        if not result.data or len(result.data) == 0:
            return (None, False)
        c = result.data[0]
        code = (c.get("referral_code") or "").strip()
        if code:
            promo_id = (c.get("stripe_referral_promotion_code_id") or "").strip()
            if not promo_id and stripe_promotion_sync:
                self._sync_stripe_referral_promotion(customer_id)
                return (code, True)
            return (code, False)
        code = self._generate_referral_code()
        try:
            self.client.table(self.table).update({
                "referral_code": code,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            if stripe_promotion_sync:
                self._sync_stripe_referral_promotion(customer_id)
            return (code, True)
        except Exception:
            return (None, False)

    def _sync_stripe_referral_promotion(self, customer_id: str) -> None:
        """Best-effort: create Stripe Promotion Code for this customer's referral_code (friend enters at Checkout)."""
        try:
            from services.stripe_referral_promotion import ensure_stripe_promotion_code_for_customer

            cust = self.get_by_id(customer_id)
            if cust:
                ensure_stripe_promotion_code_for_customer(cust)
        except Exception as e:
            print(f"[CustomerAuthService] stripe referral promotion: {e}")

    def set_stripe_referral_promotion_code_id(self, customer_id: str, promotion_code_id: str) -> bool:
        """Persist Stripe Promotion Code id (prom_xxx) after creation."""
        if not customer_id or not promotion_code_id:
            return False
        try:
            self.client.table(self.table).update(
                {
                    "stripe_referral_promotion_code_id": promotion_code_id.strip(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", str(customer_id)).execute()
            return True
        except Exception:
            return False

    def clear_stripe_referral_promotion_code_id(self, customer_id: str) -> bool:
        """Clear stored Stripe Promotion Code id so ensure_* can recreate (e.g. stale or deleted promo)."""
        if not customer_id:
            return False
        try:
            self.client.table(self.table).update(
                {
                    "stripe_referral_promotion_code_id": None,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", str(customer_id)).execute()
            return True
        except Exception:
            return False

    def create(
        self,
        email: str,
        password: str,
        referral_code: Optional[str] = None,
        *,
        marketing_opt_in: bool = False,
    ) -> Dict[str, Any]:
        """Create customer with hashed password. Raises if email exists.
        marketing_opt_in: explicit opt-in only (default False for GDPR)."""
        if not email or "@" not in email:
            raise ValueError("Valid email required")
        ok, err = validate_password(password)
        if not ok:
            raise ValueError(err)
        existing = self.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")
        pw_hash = generate_password_hash(password, method="scrypt")
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
            "marketing_opt_in": bool(marketing_opt_in),
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

    def set_email_verification_token(self, customer_id: str) -> Optional[str]:
        """Set email verification token for new signup. Returns token or None. Valid 24 hours."""
        if not customer_id:
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)
        try:
            self.client.table(self.table).update({
                "email_verification_token": token,
                "email_verification_expires": expires.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer_id).execute()
            return token
        except Exception:
            return None

    def get_by_email_verification_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get customer by valid email verification token. Returns None if expired or invalid."""
        if not token or len(token) < 20:
            return None
        try:
            result = self.client.table(self.table).select("*").eq(
                "email_verification_token", token
            ).execute()
        except Exception:
            return None
        if not result.data or len(result.data) == 0:
            return None
        c = result.data[0]
        expires = c.get("email_verification_expires")
        if expires:
            try:
                exp_str = str(expires).replace("Z", "")[:19]
                exp_dt = datetime.fromisoformat(exp_str)
                if datetime.utcnow() > exp_dt:
                    return None
            except (TypeError, ValueError):
                return None
        return c

    def confirm_email_verification(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Confirm email verification. Returns (success, customer, error_message). Clears token on success."""
        customer = self.get_by_email_verification_token(token)
        if not customer:
            return (False, None, "Invalid or expired link. Please request a new verification email.")
        try:
            self.client.table(self.table).update({
                "email_verified": True,
                "email_verification_token": None,
                "email_verification_expires": None,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer["id"]).execute()
            customer["email_verified"] = True
            return (True, customer, None)
        except Exception as e:
            return (False, None, str(e))

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

        ok, err = validate_password(new_password)
        if not ok:
            return (False, err)

        try:
            pw_hash = generate_password_hash(new_password, method="scrypt")
            new_ver = int(customer.get("auth_version") or 0) + 1
            self.client.table(self.table).update({
                "password_hash": pw_hash,
                "password_reset_token": None,
                "password_reset_expires": None,
                "auth_version": new_ver,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", customer["id"]).execute()
            return (True, None)
        except Exception as e:
            return (False, str(e))

    def change_password_with_current(
        self, customer_id: str, current_password: str, new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """Logged-in user: verify current password, set new password, bump auth_version."""
        customer = self.get_by_id(customer_id)
        if not customer:
            return (False, "Account not found.")
        if not customer.get("password_hash"):
            return (
                False,
                "You sign in with Google or Apple. Use Forgot password to set a password for this account, or keep using that sign-in method.",
            )
        if not self.verify_password(customer, current_password):
            return (False, "Current password is incorrect.")
        if current_password == new_password:
            return (False, "New password must be different from your current password.")
        ok, err = validate_password(new_password)
        if not ok:
            return (False, err)
        try:
            pw_hash = generate_password_hash(new_password, method="scrypt")
            new_ver = int(customer.get("auth_version") or 0) + 1
            self.client.table(self.table).update({
                "password_hash": pw_hash,
                "password_reset_token": None,
                "password_reset_expires": None,
                "auth_version": new_ver,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", str(customer_id)).execute()
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
