#!/usr/bin/env python3
"""
Send one test "intake link" email (same content as after payment).
Creates a real caption order so the link works. Usage: python3 send_test_intake_email.py your@email.com
"""
import sys
from dotenv import load_dotenv
load_dotenv()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 send_test_intake_email.py your@email.com")
        sys.exit(1)
    to_email = sys.argv[1].strip()

    from config import Config
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    if not Config.SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY not set in .env")
        sys.exit(1)
    if not Config.FROM_EMAIL:
        print("ERROR: FROM_EMAIL not set in .env")
        sys.exit(1)
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("ERROR: Supabase not configured (SUPABASE_URL, SUPABASE_KEY)")
        sys.exit(1)

    print(f"Creating test order and sending intake email to {to_email} ...")
    try:
        order_service = CaptionOrderService()
        order = order_service.create_order(customer_email=to_email, stripe_session_id=None)
        token = order["token"]
        base_url = (Config.BASE_URL or "http://localhost:5001").strip().rstrip("/")
        if base_url and not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = "https://" + base_url
        intake_url = f"{base_url}/captions-intake?t={token}"

        subject = "Your 30 Days of Social Media Captions — next step"
        body = f"""Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

{intake_url}

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""
        notif = NotificationService()
        ok = notif.send_email(to_email, subject, body)
        if ok:
            print("SUCCESS: Intake email sent. Check inbox/spam. The link will open the real intake form.")
        else:
            print("FAILED: Email was not sent. Check the error above.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
