"""
Configuration management for the lead capture and booking system.
Loads environment variables and provides configuration access.
"""
import os
import re
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
    
    # OpenAI (sanitize key so no newline breaks the client)
    OPENAI_API_KEY = _sanitize_header_value(os.getenv('OPENAI_API_KEY', '') or '')
    OPENAI_MODEL = (os.getenv('OPENAI_MODEL') or 'gpt-4o-mini').strip()  # Using mini for cost efficiency
    
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
    FROM_EMAIL = _sanitize_header_value(os.getenv('FROM_EMAIL', '') or '') or 'noreply@example.com'
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

    # Digital Front Desk inbound (auto-reply). Domain for unique addresses, e.g. inbound.lumo22.com. MX must point to SendGrid.
    INBOUND_EMAIL_DOMAIN = (os.getenv('INBOUND_EMAIL_DOMAIN', '').strip() or 'inbound.lumo22.com').lower()

    # Cron job auth: shared secret for /api/captions-send-reminders (Railway cron). Generate with: openssl rand -hex 32
    CRON_SECRET = _sanitize_header_value(os.getenv('CRON_SECRET', '').strip() or '')

    # Site chat widget: key for the Lumo 22 marketing site's own chat bubble (demo + help). When set, widget appears and status endpoint returns valid.
    SITE_CHAT_WIDGET_KEY = (os.getenv('SITE_CHAT_WIDGET_KEY', '').strip() or None)

    # Qualification Settings
    MIN_QUALIFICATION_SCORE = int(os.getenv('MIN_QUALIFICATION_SCORE', '60'))
    AUTO_BOOK_ENABLED = os.getenv('AUTO_BOOK_ENABLED', 'True').lower() == 'true'
    
    @staticmethod
    def validate():
        """Validate that required configuration is present"""
        required = ['OPENAI_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY']
        missing = [key for key in required if not getattr(Config, key)]
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
