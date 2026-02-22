#!/usr/bin/env python3
"""
Run the same steps as the Stripe webhook handler locally.
Use this to see the REAL error in your terminal (the one Stripe reports as "Handler failed").

Usage: python3 test_webhook_handler.py your@email.com

Uses your .env (Supabase, SendGrid). If it fails here, it fails on Railway too.
"""
import sys
from dotenv import load_dotenv
load_dotenv()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_webhook_handler.py your@email.com")
        print("Example: python3 test_webhook_handler.py skoverment@gmail.com")
        sys.exit(1)
    customer_email = sys.argv[1].strip()

    # Fake session like Stripe sends (same shape the webhook uses)
    session = {
        "id": "cs_test_fake_for_local_test",
        "customer_details": {"email": customer_email},
        "metadata": {"product": "captions"},
    }

    print("Running webhook handler steps (create order + send intake email)...")
    print("-" * 50)

    try:
        from services.caption_order_service import CaptionOrderService
        from services.notifications import NotificationService

        print("1. Creating order in Supabase...")
        order_service = CaptionOrderService()
        order = order_service.create_order(
            customer_email=customer_email,
            stripe_session_id=session.get("id"),
        )
        token = order["token"]
        print(f"   OK - order id={order.get('id')} token=...{token[-6:]}")

        print("2. Sending intake email...")
        INTAKE_BASE = "https://lumo-22-production.up.railway.app"
        intake_url = f"{INTAKE_BASE}/captions-intake?t={token}"
        subject = "Your 30 Days of Social Media Captions - next step"
        body = f"""Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

{intake_url}

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""
        notif = NotificationService()
        ok = notif.send_email(customer_email, subject, body)
        if ok:
            print("   OK - Email sent.")
        else:
            print("   FAILED - SendGrid returned False (check logs above).")

        print("-" * 50)
        print("SUCCESS. If this worked locally, the same code should work on Railway after redeploy.")
    except Exception as e:
        print("-" * 50)
        print("FAILED. This is the error Stripe sees as 'Handler failed':")
        print()
        print(f"  {type(e).__name__}: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
