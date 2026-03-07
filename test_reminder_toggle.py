#!/usr/bin/env python3
"""
Test that reminder on/off toggle works correctly.

1. Create subscription order (default: reminders ON)
2. Turn reminders OFF -> _should_send_reminder returns False
3. Turn reminders ON -> _should_send_reminder returns True

Usage: python3 test_reminder_toggle.py

Requires: .env with Supabase config.
"""
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    test_email = "reminder-toggle-test@example.com"
    test_sub_id = "sub_test_reminder_toggle_do_not_use"
    period_end_ts = 9999999999  # arbitrary, for _should_send_reminder

    print("Testing reminder on/off toggle...")
    print("-" * 50)

    try:
        from services.caption_order_service import CaptionOrderService
        from services.caption_reminder_service import _should_send_reminder

        svc = CaptionOrderService()

        # 1. Create subscription order (reminders ON by default)
        print("1. Creating subscription order (reminders ON by default)...")
        order = svc.create_order(
            customer_email=test_email,
            stripe_subscription_id=test_sub_id,
            stripe_session_id=None,
        )
        order_id = order["id"]
        print(f"   OK - order id={order_id}")

        # Fetch full order (create_order returns basic fields; get_by_id has reminder_opt_out)
        order = svc.get_by_id(order_id)
        if not order:
            print("   FAILED: Could not fetch order")
            sys.exit(1)

        # 2. Default: reminders ON (reminder_opt_out=False)
        print("2. Checking default: reminders ON...")
        opt_out = order.get("reminder_opt_out")
        if opt_out is True:
            print("   FAILED: Default reminder_opt_out should be False")
            sys.exit(1)
        should_send = _should_send_reminder(order, period_end_ts)
        if not should_send:
            print("   FAILED: _should_send_reminder should be True when opt_out=False")
            sys.exit(1)
        print("   OK - would send reminder")

        # 3. Turn reminders OFF
        print("3. Turning reminders OFF...")
        ok = svc.update(order_id, {"reminder_opt_out": True})
        if not ok:
            print("   FAILED: update returned False")
            sys.exit(1)
        order = svc.get_by_id(order_id)
        should_send = _should_send_reminder(order, period_end_ts)
        if should_send:
            print("   FAILED: _should_send_reminder should be False when opt_out=True")
            sys.exit(1)
        print("   OK - would NOT send reminder")

        # 4. Turn reminders ON again
        print("4. Turning reminders ON again...")
        ok = svc.update(order_id, {"reminder_opt_out": False})
        if not ok:
            print("   FAILED: update returned False")
            sys.exit(1)
        order = svc.get_by_id(order_id)
        should_send = _should_send_reminder(order, period_end_ts)
        if not should_send:
            print("   FAILED: _should_send_reminder should be True when opt_out=False")
            sys.exit(1)
        print("   OK - would send reminder")

        # Cleanup
        print("5. Cleanup: deleting test order...")
        svc.delete_by_customer_email(test_email)
        print("   OK")

        print("-" * 50)
        print("SUCCESS. Reminder toggle works: OFF -> ON -> OFF.")
    except Exception as e:
        print("-" * 50)
        print("FAILED:")
        print(f"  {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
