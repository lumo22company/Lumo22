"""
Configuration management for Lumo 22 (Captions product).
Loads environment variables and provides configuration access.
"""
import os
import re
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _sanitize_url(raw: str) -> str:
    """Strip and remove control chars so httpx/urlparse don't raise InvalidURL."""
    if not raw or not isinstance(raw, str):
        return (raw or "").strip() or ""
    s = re.sub(r"[\x00-\x1f\x7f]", "", raw.strip())
    return s.rstrip("/").strip()


def _sanitize_header_value(raw: str) -> str:
    """Strip and remove control chars so header values (e.g. Bearer token) don't raise Invalid header value."""
    if not raw or not isinstance(raw, str):
        return (raw or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (raw or "").strip())


class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    # Session cookie: SameSite Lax so login persists after redirect. Secure=True in production (HTTPS).
    SESSION_COOKIE_SECURE = False  # Overridden in app.py when is_production()
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)  # Inactivity logout: session expires after 1 hour of no requests
    
    # AI Provider: "openai" or "anthropic". When anthropic, caption generation uses Claude.
    AI_PROVIDER = (os.getenv('AI_PROVIDER') or 'openai').strip().lower()
    # OpenAI (sanitize key so no newline breaks the client)
    OPENAI_API_KEY = _sanitize_header_value(os.getenv('OPENAI_API_KEY', '') or '')
    OPENAI_MODEL = (os.getenv('OPENAI_MODEL') or 'gpt-4o-mini').strip()  # Using mini for cost efficiency
    # Anthropic (for AI_PROVIDER=anthropic)
    ANTHROPIC_API_KEY = _sanitize_header_value(os.getenv('ANTHROPIC_API_KEY', '') or '')
    ANTHROPIC_MODEL = (os.getenv('ANTHROPIC_MODEL') or 'claude-haiku-4-5-20251001').strip()
    
    # Supabase (sanitize URL so httpx doesn't raise InvalidURL from env newlines)
    SUPABASE_URL = _sanitize_url(os.getenv('SUPABASE_URL', '') or '')
    SUPABASE_KEY = (os.getenv('SUPABASE_KEY') or '').strip()
    # Service role bypasses RLS; required for appointments table (slot availability)
    SUPABASE_SERVICE_ROLE_KEY = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
    
    # Calendly
    CALENDLY_API_KEY = os.getenv('CALENDLY_API_KEY')
    CALENDLY_EVENT_TYPE_ID = os.getenv('CALENDLY_EVENT_TYPE_ID')
    CALENDLY_BASE_URL = 'https://api.calendly.com'
    
    # SendGrid (sanitize key so Authorization header doesn't get Invalid header value from env newline)
    SENDGRID_API_KEY = _sanitize_header_value(os.getenv('SENDGRID_API_KEY', '') or '')
    # Use noreply@lumo22.com so SendGrid can verify; never use @example.com (undeliverable)
    FROM_EMAIL = _sanitize_header_value(os.getenv('FROM_EMAIL', '') or '') or 'noreply@lumo22.com'
    FROM_NAME = _sanitize_header_value(os.getenv('FROM_NAME', '') or '') or 'Lumo 22'
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Business Settings
    BUSINESS_NAME = os.getenv('BUSINESS_NAME', 'Service Business')
    BUSINESS_PHONE = os.getenv('BUSINESS_PHONE', '')
    BOOKING_TIMEZONE = os.getenv('BOOKING_TIMEZONE', 'UTC')
    
    # Activation / payment (Digital Front Desk). Single link or per-plan Stripe/payment links.
    ACTIVATION_LINK = os.getenv('ACTIVATION_LINK', '').strip() or None
    ACTIVATION_LINK_STARTER = os.getenv('ACTIVATION_LINK_STARTER', '').strip() or None
    ACTIVATION_LINK_STANDARD = os.getenv('ACTIVATION_LINK_STANDARD', '').strip() or None
    ACTIVATION_LINK_PREMIUM = os.getenv('ACTIVATION_LINK_PREMIUM', '').strip() or None
    # Chat Assistant: standalone product. Per-tier Stripe Payment Links.
    CHAT_PAYMENT_LINK = os.getenv('CHAT_PAYMENT_LINK', '').strip() or None
    CHAT_PAYMENT_LINK_STARTER = os.getenv('CHAT_PAYMENT_LINK_STARTER', '').strip() or None
    CHAT_PAYMENT_LINK_GROWTH = os.getenv('CHAT_PAYMENT_LINK_GROWTH', '').strip() or None
    CHAT_PAYMENT_LINK_PRO = os.getenv('CHAT_PAYMENT_LINK_PRO', '').strip() or None
    # Email + Chat bundle: per-email-tier Stripe Payment Links (Starter+chat, Standard+chat, Premium+chat).
    ACTIVATION_LINK_STARTER_BUNDLE = os.getenv('ACTIVATION_LINK_STARTER_BUNDLE', '').strip() or None
    ACTIVATION_LINK_STANDARD_BUNDLE = os.getenv('ACTIVATION_LINK_STANDARD_BUNDLE', '').strip() or None
    ACTIVATION_LINK_PREMIUM_BUNDLE = os.getenv('ACTIVATION_LINK_PREMIUM_BUNDLE', '').strip() or None

    # 30 Days Captions product (Stripe payment link for one-time purchase)
    CAPTIONS_PAYMENT_LINK = os.getenv('CAPTIONS_PAYMENT_LINK', '').strip() or None
    # Stripe secret key (sk_test_ or sk_live_) — needed to create Checkout Sessions for redirect-to-intake flow
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip() or None
    # Stripe webhook secret (for captions automation); create in Stripe Dashboard → Developers → Webhooks
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip() or None
    # Base URL of your site (for intake/delivery links in emails), e.g. https://lumo22.com
    # Remove any non-printable chars (e.g. newline from env) so URLs are valid
    _base = os.getenv('BASE_URL', 'http://localhost:5001').strip().rstrip('/')
    BASE_URL = re.sub(r'[\x00-\x1f\x7f]', '', _base) if _base else ''
    # Stripe Price ID for 30 Days Captions one-off (price_xxx); required for Checkout Session. GBP.
    STRIPE_CAPTIONS_PRICE_ID = os.getenv('STRIPE_CAPTIONS_PRICE_ID', '').strip() or None
    # Optional: same product in USD and EUR (enables currency selector on /captions).
    STRIPE_CAPTIONS_PRICE_ID_USD = os.getenv('STRIPE_CAPTIONS_PRICE_ID_USD', '').strip() or None
    STRIPE_CAPTIONS_PRICE_ID_EUR = os.getenv('STRIPE_CAPTIONS_PRICE_ID_EUR', '').strip() or None
    # Stripe Price ID for 30 Days Captions subscription £79/month (price_xxx); optional, for subscription option on /captions
    STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID = os.getenv('STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID', '').strip() or None
    STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD = os.getenv('STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD', '').strip() or None
    STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR = os.getenv('STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR', '').strip() or None
    # Extra platform add-on: one-off £29, subscription £19/mo (price_xxx each). Optional; if set, checkout accepts ?platforms=N.
    STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID = os.getenv('STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID', '').strip() or None
    STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID = os.getenv('STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID', '').strip() or None
    # Stories add-on: one-off £29, subscription £17/mo. Optional; when set, product page shows Stories option when IG & Facebook selected.
    STRIPE_CAPTIONS_STORIES_PRICE_ID = os.getenv('STRIPE_CAPTIONS_STORIES_PRICE_ID', '').strip() or None
    STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID = os.getenv('STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID', '').strip() or None
    # Refer-a-friend: Stripe Coupon ID (e.g. 10% off once). Used to create one Promotion Code per customer; friends enter the code on Stripe Checkout.
    STRIPE_REFERRAL_COUPON_ID = os.getenv('STRIPE_REFERRAL_COUPON_ID', '').strip() or None

    # Digital Front Desk inbound (auto-reply). Domain for unique addresses, e.g. inbound.lumo22.com. MX must point to SendGrid.
    INBOUND_EMAIL_DOMAIN = (os.getenv('INBOUND_EMAIL_DOMAIN', '').strip() or 'inbound.lumo22.com').lower()

    # One-off upgrade reminder: days before "day 30" to send (3 or 5). Pack "finishes" 30 days after delivery; we send at 27 or 25 days after delivery.
    ONE_OFF_UPGRADE_REMINDER_DAYS_BEFORE = max(1, min(14, int(os.getenv('ONE_OFF_UPGRADE_REMINDER_DAYS_BEFORE', '5'))))

    # Cron job auth: shared secret for /api/captions-send-reminders (Railway cron). Generate with: openssl rand -hex 32
    CRON_SECRET = _sanitize_header_value(os.getenv('CRON_SECRET', '').strip() or '')
    # Test endpoint: secret for /api/captions-deliver-test (triggers generation). If set, ?secret=XXX required. In production, set this.
    CAPTIONS_DELIVER_TEST_SECRET = _sanitize_header_value(os.getenv('CAPTIONS_DELIVER_TEST_SECRET', '').strip() or '')

    @staticmethod
    def is_production():
        """True if we should enforce production config (SECRET_KEY changed from default or FLASK_ENV=production)."""
        default_secret = 'dev-secret-key-change-in-production'
        secret = (os.getenv('SECRET_KEY') or '').strip()
        env = (os.getenv('FLASK_ENV') or 'development').strip().lower()
        return (secret and secret != default_secret) or env == 'production'

    @staticmethod
    def validate_ai_provider_env():
        """
        Fail fast on common Railway/host mistakes: API key pasted into AI_PROVIDER.
        Called on app import (Gunicorn/Railway), not only when running `python app.py`.

        AI_PROVIDER must be exactly 'anthropic' or 'openai' (case-insensitive), or unset (defaults to openai).
        In production, the matching API key must be set.
        """
        raw = (os.getenv("AI_PROVIDER") or "").strip()
        if raw:
            lowered = raw.lower()
            if lowered not in ("anthropic", "openai"):
                hint = ""
                if raw.startswith("sk-ant") or (
                    raw.startswith("sk-") and len(raw) > 20
                ):
                    hint = (
                        " This value looks like an API key. Set AI_PROVIDER to the word anthropic or openai only, "
                        "and put the secret in ANTHROPIC_API_KEY or OPENAI_API_KEY."
                    )
                preview = raw[:28] + ("…" if len(raw) > 28 else "")
                raise ValueError(
                    f"Invalid AI_PROVIDER (got {preview!r}). "
                    f"Must be exactly 'anthropic' or 'openai', not a secret key.{hint}"
                )

        effective = (raw or "openai").strip().lower()
        if Config.is_production():
            if effective == "anthropic":
                if not (Config.ANTHROPIC_API_KEY or "").strip():
                    raise ValueError(
                        "Production: ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic."
                    )
            else:
                if not (Config.OPENAI_API_KEY or "").strip():
                    raise ValueError(
                        "Production: OPENAI_API_KEY is required when AI_PROVIDER is openai or unset (default). "
                        "If you use Anthropic only, set AI_PROVIDER=anthropic and ANTHROPIC_API_KEY."
                    )

    @staticmethod
    def validate_ai_vendor_optional():
        """
        Optional Railway sanity variable: AI_VENDOR=anthropic|openai (plain text, not secret).
        If set, must match the effective provider from AI_PROVIDER (or default openai when unset).
        Logs WARNING only — does not exit (AI_PROVIDER validation already ran).
        """
        import sys

        v = (os.getenv("AI_VENDOR") or "").strip().lower()
        if not v:
            return
        if v not in ("anthropic", "openai"):
            print(
                f"[Config] WARNING: AI_VENDOR={v!r} must be 'anthropic' or 'openai' if set; ignoring.",
                file=sys.stderr,
            )
            return
        raw_ap = (os.getenv("AI_PROVIDER") or "").strip()
        effective = (raw_ap or "openai").strip().lower()
        if v != effective:
            print(
                f"[Config] WARNING: AI_VENDOR={v!r} does not match effective AI provider {effective!r} "
                f"(from AI_PROVIDER). In Railway, the variable list often masks values — use Edit to confirm AI_PROVIDER.",
                file=sys.stderr,
            )

    @staticmethod
    def log_ai_provider_summary():
        """One startup line for deploy logs: effective provider and which keys are set (never prints secrets)."""
        raw_ap = (os.getenv("AI_PROVIDER") or "").strip()
        effective = (raw_ap or "openai").strip().lower()
        v = (os.getenv("AI_VENDOR") or "").strip()
        has_ant = bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())
        has_oai = bool((os.getenv("OPENAI_API_KEY") or "").strip())
        ap_note = repr(raw_ap) if raw_ap else "(unset — defaults to openai)"
        vendor_note = repr(v) if v else "(optional, not set)"
        print(
            f"[Config] AI summary: AI_PROVIDER={ap_note} → effective={effective!r} | "
            f"AI_VENDOR={vendor_note} | ANTHROPIC_API_KEY set={has_ant} | OPENAI_API_KEY set={has_oai}",
            flush=True,
        )

    @staticmethod
    def validate():
        """Validate that required configuration is present. Stricter in production."""
        Config.validate_ai_provider_env()
        required = ['SUPABASE_URL', 'SUPABASE_KEY']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        if Config.is_production():
            production_required = [
                'SECRET_KEY',
                'STRIPE_SECRET_KEY',
                'STRIPE_WEBHOOK_SECRET',
                'SENDGRID_API_KEY',
                'BASE_URL',
            ]
            default_secret = 'dev-secret-key-change-in-production'
            prod_missing = []
            for key in production_required:
                val = getattr(Config, key, None)
                if key == 'SECRET_KEY' and (not val or (val == default_secret)):
                    prod_missing.append(key)
                elif not val or (isinstance(val, str) and not val.strip()):
                    prod_missing.append(key)
            if prod_missing:
                raise ValueError(
                    f"Production missing required configuration: {', '.join(prod_missing)}. "
                    "Set these in your host (e.g. Railway) Variables. See PRODUCTION_ENV_SETUP.md."
                )

        return True
