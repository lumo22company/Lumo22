#!/usr/bin/env python3
"""
Test that deleted-account blocklist works and resubscribe removes from blocklist.

1. Add email to blocklist -> reminder service skips it
2. Create new order with that email -> email removed from blocklist (resubscribe flow)

Usage: python3 test_deleted_account_blocklist.py

Requires: .env with Supabase config, and deleted_account_emails table (run database_deleted_account_emails.sql).
"""
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    test_email = "blocklist-test-resubscribe@example.com"
    print("Testing deleted-account blocklist + resubscribe removal...")
    print("-" * 50)

    try:
        from services.caption_order_service import CaptionOrderService

        svc = CaptionOrderService()

        # 1. Add to blocklist (simulate account deletion)
        print("1. Adding email to blocklist (simulate account delete)...")
        ok = svc.add_to_deleted_blocklist(test_email)
        if not ok:
            print("   FAILED: add_to_deleted_blocklist returned False")
            sys.exit(1)
        print("   OK")

        # 2. Verify it's in blocklist
        print("2. Checking email is in blocklist...")
        blocked = svc.get_deleted_account_emails()
        if test_email.lower() not in blocked:
            print(f"   FAILED: {test_email} not in blocklist (got {len(blocked)} emails)")
            sys.exit(1)
        print("   OK - reminder service would skip this email")

        # 3. Create new order (simulate resubscribe) -> should remove from blocklist
        print("3. Creating new order (simulate resubscribe)...")
        order = svc.create_order(customer_email=test_email, stripe_session_id=None)
        print(f"   OK - order id={order.get('id')}")

        # 4. Verify removed from blocklist
        print("4. Checking email removed from blocklist...")
        blocked_after = svc.get_deleted_account_emails()
        if test_email.lower() in blocked_after:
            print(f"   FAILED: {test_email} still in blocklist after create_order")
            sys.exit(1)
        print("   OK - reminder service will send to this email")

        # Cleanup: delete test order so we don't leave junk
        print("5. Cleanup: deleting test order...")
        svc.delete_by_customer_email(test_email)
        print("   OK")

        print("-" * 50)
        print("SUCCESS. Blocklist add + resubscribe removal works.")
    except Exception as e:
        print("-" * 50)
        print("FAILED:")
        print(f"  {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
