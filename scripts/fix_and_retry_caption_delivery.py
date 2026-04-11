#!/usr/bin/env python3
"""
Fix one order so it appears on your account, then re-run caption generation and send the PDF email.

Use this when:
- You completed the intake form but never got the PDF email, and/or
- The order doesn't show on your account history.

You need the TOKEN from your intake form link (the email that says "Complete the form").
The link looks like: https://yoursite.com/captions-intake?t=XXXXXXXX
                                                      copy this part ^^^^^^^^

Before retrying after a DB error: apply database_caption_orders_delivery_archive.sql in Supabase
so caption_orders.delivery_archive exists.

Usage (from project root, with .env matching production — SUPABASE_URL, SUPABASE_KEY, AI + SendGrid keys):
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

    # 2) Run generation and delivery (same as /api/account/retry-caption-delivery).
    # force_redeliver=True for failed or generating so we don't no-op (matches "Try sending my pack again").
    force_redeliver = status in ("failed", "generating")
    print("Running caption generation and sending delivery email ...")
    try:
        from api.captions_routes import _run_generation_and_deliver
        ok, err = _run_generation_and_deliver(str(order_id), force_redeliver=force_redeliver)
        print()
        if status == "delivered" and not force_redeliver:
            print(
                "This order is already marked delivered, so no new generation was started.\n"
                "If the PDF never arrived, check spam; open your Lumo account for backup download links;\n"
                "or ask support to resend the delivery email for this order."
            )
        elif ok and not err:
            print("Done. Check your inbox (and spam) for the PDF. Refresh your account page to see this order.")
        elif ok and err:
            print(f"Pack saved but email may have failed: {err}\nUse your account backup links or ask support to resend.")
        else:
            print(f"Delivery did not complete: {err or 'unknown error'}")
            sys.exit(1)
    except Exception as e:
        print()
        print(f"Delivery failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
