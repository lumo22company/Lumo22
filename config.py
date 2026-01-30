"""
Configuration management for the lead capture and booking system.
Loads environment variables and provides configuration access.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # Using mini for cost efficiency
    
    # Supabase
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Calendly
    CALENDLY_API_KEY = os.getenv('CALENDLY_API_KEY')
    CALENDLY_EVENT_TYPE_ID = os.getenv('CALENDLY_EVENT_TYPE_ID')
    CALENDLY_BASE_URL = 'https://api.calendly.com'
    
    # SendGrid
    SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
    FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@example.com')
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Business Settings
    BUSINESS_NAME = os.getenv('BUSINESS_NAME', 'Service Business')
    BUSINESS_PHONE = os.getenv('BUSINESS_PHONE', '')
    BOOKING_TIMEZONE = os.getenv('BOOKING_TIMEZONE', 'UTC')
    
    # Activation / payment (link shown on /activate page; update here, email links to site)
    ACTIVATION_LINK = os.getenv('ACTIVATION_LINK', '').strip() or None

    # 30 Days Captions product (Stripe payment link for one-time purchase)
    CAPTIONS_PAYMENT_LINK = os.getenv('CAPTIONS_PAYMENT_LINK', '').strip() or None
    # Stripe webhook secret (for captions automation); create in Stripe Dashboard → Developers → Webhooks
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip() or None
    # Base URL of your site (for intake/delivery links in emails), e.g. https://lumo22.com
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5001').strip().rstrip('/')
    # Optional: Stripe Price ID for 30 Days Captions (to only handle this product in webhook)
    STRIPE_CAPTIONS_PRICE_ID = os.getenv('STRIPE_CAPTIONS_PRICE_ID', '').strip() or None

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
