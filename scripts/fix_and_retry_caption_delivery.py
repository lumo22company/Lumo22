#!/usr/bin/env python3
"""
Fix one order so it appears on your account, then re-run caption generation and send the PDF email.

Use this when:
- You completed the intake form but never got the PDF email, and/or
- The order doesn't show on your account history.

You need the TOKEN from your intake form link (the email that says "Complete the form").
The link looks like: https://yoursite.com/captions-intake?t=XXXXXXXX
                                                      copy this part ^^^^^^^^

Usage (from project root, with .env set):
  python3 scripts/fix_and_retry_caption_delivery.py YOUR_TOKEN

Example:
  python3 scripts/fix_and_retry_caption_delivery.py abc123XYZ_def456

What it does:
  1. Loads your order by token
  2. Saves the order's email in lowercase so your account page finds it
  3. Re-runs caption generation and sends the delivery email (PDF) to that email
"""
import sys
import os

# Run from repo root so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python3 scripts/fix_and_retry_caption_delivery.py YOUR_TOKEN")
        sys.exit(1)

    token = (sys.argv[1] or "").strip()
    if not token:
        print("ERROR: Provide the token from your intake link (the part after ?t=)")
        sys.exit(1)

    from config import Config
    from services.caption_order_service import CaptionOrderService

    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in .env")
        sys.exit(1)

    order_service = CaptionOrderService()
    order = order_service.get_by_token(token)
    if not order:
        print(f"ERROR: No order found for this token. Check that you copied the full token from the intake link.")
        sys.exit(1)

    order_id = order.get("id")
    email = (order.get("customer_email") or "").strip()
    if not email or "@" not in email:
        print("ERROR: Order has no customer email. Contact support.")
        sys.exit(1)

    intake = order.get("intake")
    if not intake or not isinstance(intake, dict):
        print("ERROR: This order has no intake data. Complete the intake form first using the link from your email, then run this script again.")
        sys.exit(1)

    status = (order.get("status") or "").strip()
    print(f"Order id: {order_id}")
    print(f"Email:    {email}")
    print(f"Status:   {status}")
    print()

    # 1) Normalize email to lowercase so account page finds the order
    email_lower = email.strip().lower()
    if email != email_lower:
        ok = order_service.update(str(order_id), {"customer_email": email_lower})
        if ok:
            print("Fixed: customer_email saved in lowercase so it will show on your account.")
        else:
            print("Warning: could not update email to lowercase (order will still be fixed for delivery).")
    else:
        print("Email already lowercase; account should show this order after refresh.")

    # 2) Run generation and delivery (same as after form submit)
    print("Running caption generation and sending delivery email ...")
    try:
        from api.captions_routes import _run_generation_and_deliver
        _run_generation_and_deliver(str(order_id))
        print()
        print("Done. Check your inbox (and spam) for the PDF. Refresh your account page to see this order.")
    except Exception as e:
        print()
        print(f"Delivery failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
