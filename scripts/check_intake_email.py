#!/usr/bin/env python3
"""
Verify intake email setup (SendGrid + FROM_EMAIL). Optionally send a test intake email.
Run locally: python3 scripts/check_intake_email.py
Send test to your address: python3 scripts/check_intake_email.py your@email.com
"""
import os
import sys

# Load env from project root
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

def main():
    from dotenv import load_dotenv
    load_dotenv()

    from config import Config

    send_to = (sys.argv[1].strip() if len(sys.argv) > 1 else None)

    print("Intake email setup check")
    print("-" * 40)

    ok = True
    key = (Config.SENDGRID_API_KEY or "").strip()
    if not key:
        print("  SENDGRID_API_KEY: NOT SET")
        ok = False
    else:
        print("  SENDGRID_API_KEY: set (length {})".format(len(key)))

    from_email = (Config.FROM_EMAIL or "").strip()
    if not from_email:
        print("  FROM_EMAIL: NOT SET (defaults to noreply@lumo22.com in code)")
    else:
        print("  FROM_EMAIL: {}".format(from_email))

    base = (Config.BASE_URL or "").strip()
    if not base:
        print("  BASE_URL: NOT SET (intake links may use fallback)")
    else:
        print("  BASE_URL: {}".format(base[:50] + "..." if len(base) > 50 else base))

    if not ok:
        print("\nFix: Set SENDGRID_API_KEY and optionally FROM_EMAIL in Railway (or .env).")
        print("  In SendGrid: verify the FROM_EMAIL address (Settings → Sender Authentication).")
        sys.exit(1)

    print("\n  Config looks OK for sending intake emails.")

    if send_to:
        print("\nSending test intake email to {} ...".format(send_to))
        try:
            from services.caption_order_service import CaptionOrderService
            from services.notifications import NotificationService

            if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
                print("  SUPABASE_URL/SUPABASE_KEY not set; cannot create test order. Skipping send.")
                sys.exit(0)
            order_service = CaptionOrderService()
            order = order_service.create_order(customer_email=send_to, stripe_session_id=None)
            token = (order.get("token") or "").strip()
            base = (Config.BASE_URL or "").strip().rstrip("/") or "https://lumo-22-production.up.railway.app"
            if base and not base.startswith("http"):
                base = "https://" + base
            intake_url = base + "/captions-intake?t=" + token
            notif = NotificationService()
            ok = notif.send_intake_link_email(send_to, intake_url)
            if ok:
                print("  Done. Check inbox (and spam) for the intake link.")
            else:
                print("  SendGrid returned failure. Check SendGrid Activity and FROM_EMAIL verification.")
                sys.exit(1)
        except Exception as e:
            print("  Error: {}".format(e))
            sys.exit(1)
    else:
        print("\nTo send a test intake email: python3 scripts/check_intake_email.py your@email.com")

if __name__ == "__main__":
    main()
