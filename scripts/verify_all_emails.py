#!/usr/bin/env python3
"""
Verify all Lumo 22 email templates produce non-empty content.
Run: python3 scripts/verify_all_emails.py
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

def main():
    from dotenv import load_dotenv
    load_dotenv()

    from services.notifications import (
        _password_reset_email_html,
        _email_change_verification_html,
        _intake_link_email_html,
        _captions_delivery_email_html,
        _captions_reminder_email_html,
        _captions_intake_reminder_email_html,
        _welcome_and_verify_email_html,
        _order_receipt_email_html,
        _plan_change_confirmation_email_html,
        _subscription_cancelled_email_html,
        _branded_html_email,
    )

    errors = []
    passed = 0

    def check(name: str, html: str, min_len: int = 50) -> None:
        nonlocal passed, errors
        h = (html or "").strip()
        if not h:
            errors.append(f"{name}: HTML is empty")
            return
        if len(h) < min_len:
            errors.append(f"{name}: HTML too short ({len(h)} chars)")
            return
        if "Lumo 22" not in h:
            errors.append(f"{name}: missing Lumo 22 branding")
            return
        passed += 1

    base = "https://www.lumo22.com"

    # 1. Order receipt
    html = _order_receipt_email_html("• Subscription (£79/mo)\n• 2 platforms", "£96.00")
    check("Order receipt (with details)", html)
    html = _order_receipt_email_html(None, None)
    check("Order receipt (no details)", html)

    # 2. Intake link
    html = _intake_link_email_html(f"{base}/captions-intake?t=x", "• One-off (£97)", False)
    check("Intake link", html)

    # 3. Captions delivery
    for has_stories, has_sub in [(False, False), (True, False), (False, True)]:
        html = _captions_delivery_email_html(has_stories, has_sub)
        check(f"Captions delivery (stories={has_stories}, sub={has_sub})", html)

    # 4. Pre-pack reminder
    html = _captions_reminder_email_html(f"{base}/captions-intake?t=x", f"{base}/account")
    check("Pre-pack reminder", html)

    # 5. Intake reminder (awaiting_intake)
    html = _captions_intake_reminder_email_html(f"{base}/captions-intake?t=x")
    check("Intake reminder (awaiting)", html)

    # 6. Plan change (upgrade)
    html = _plan_change_confirmation_email_html(
        "What changed: 30 Days Story Ideas has been added.",
        "Stories will be included in your next pack.",
        f"{base}/account",
        new_price_display="£96",
        old_price_display="£79",
    )
    check("Plan change (upgrade)", html)

    # 7. Plan change (reduce)
    html = _plan_change_confirmation_email_html(
        "What changed: your subscription now includes 1 platform instead of 3.",
        "Changes apply to your next pack.",
        f"{base}/account",
        new_price_display="£79",
        old_price_display="£115",
    )
    check("Plan change (reduce)", html)

    # 8. Subscription cancelled
    html = _subscription_cancelled_email_html(f"{base}/captions")
    check("Subscription cancelled", html)

    # 9. Welcome + verify
    html = _welcome_and_verify_email_html(f"{base}/verify-email?token=x")
    check("Welcome + verify", html)

    # 10. Password reset
    html = _password_reset_email_html(f"{base}/reset-password?token=x")
    check("Password reset", html)

    # 11. Email change verification
    html = _email_change_verification_html(f"{base}/change-email-confirm?token=x")
    check("Email change verification", html)

    # 12. Branded fallback
    html = _branded_html_email("Hi,\n\nTest.\n\n— Lumo 22")
    check("Branded HTML fallback", html)

    print("=" * 60)
    print("Lumo 22 Email Verification")
    print("=" * 60)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        print("=" * 60)
        print(f"FAILED: {len(errors)} issue(s), {passed} passed")
        sys.exit(1)
    print(f"  OK: All {passed} email templates produce non-empty content")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
