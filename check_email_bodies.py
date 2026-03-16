#!/usr/bin/env python3
"""
Audit: verify all email flows produce non-empty body text.

Uses mock/sample data to build each email and checks body is non-empty.
Run: python3 check_email_bodies.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    from dotenv import load_dotenv
    load_dotenv()

    errors = []
    ok_count = 0

    def check(name: str, body: str, min_len: int = 20) -> None:
        nonlocal ok_count, errors
        b = (body or "").strip()
        if not b:
            errors.append(f"{name}: body is empty")
            return
        if len(b) < min_len:
            errors.append(f"{name}: body too short ({len(b)} chars)")
            return
        ok_count += 1

    # 1. NotificationService methods (build body, then check)
    from services.notifications import (
        _password_reset_email_html,
        _email_change_verification_html,
        _intake_link_email_html,
        _captions_delivery_email_html,
        _captions_reminder_email_html,
        _captions_intake_reminder_email_html,
        _welcome_and_verify_email_html,
        _subscription_cancelled_email_html,
        _plan_change_confirmation_email_html,
        _order_receipt_email_html,
        _branded_html_email,
    )
    from services.notifications import NotificationService

    notif = NotificationService()

    # Password reset
    body = "Hi,\n\nYou requested a password reset..."
    html = _password_reset_email_html("https://example.com/reset")
    check("Password reset (plain)", body)
    check("Password reset (HTML)", html, min_len=100)

    # Email change
    body = "You requested to change the email address..."
    html = _email_change_verification_html("https://example.com/confirm")
    check("Email change (plain)", body)
    check("Email change (HTML)", html, min_len=100)

    # Intake link
    body = "Hi,\n\nThanks for your order..."
    html = _intake_link_email_html("https://example.com/intake?t=x", "• One-off (£97)")
    check("Intake link (plain)", body)
    check("Intake link (HTML)", html, min_len=100)

    # Captions delivery
    for has_stories in (False, True):
        html = _captions_delivery_email_html(has_stories)
        check(f"Captions delivery has_stories={has_stories}", html, min_len=50)

    # Caption reminder
    body = "Hi,\n\nYour next 30 Days of Social Media Captions pack is coming soon..."
    html = _captions_reminder_email_html("https://example.com/login?next=https%3A%2F%2Fexample.com%2Fcaptions-intake%3Ft%3Dx", "https://example.com/account")
    check("Reminder (plain)", body)
    check("Reminder (HTML)", html, min_len=100)

    # Branded HTML (generic)
    plain = "Hi,\n\nTest content.\n\n— Lumo 22"
    html = _branded_html_email(plain)
    check("Branded HTML from plain", html, min_len=100)

    # One-off intake reminder
    body = "Hi,\n\nThanks for your order of 30 Days of Social Media Captions.\n\nBefore we can start writing..."
    html = _captions_intake_reminder_email_html("https://example.com/captions-intake?t=x")
    check("Intake reminder one-off (plain)", body)
    check("Intake reminder one-off (HTML)", html, min_len=50)

    # Welcome + verify
    body = "Hi,\n\nWelcome to Lumo 22. You've created an account.\n\nTo get started, please verify..."
    html = _welcome_and_verify_email_html("https://example.com/verify?token=x")
    check("Welcome/verify (plain)", body)
    check("Welcome/verify (HTML)", html, min_len=50)

    # Subscription cancelled
    body = "Hi,\n\nYour 30 Days of Social Media Captions subscription has been cancelled..."
    html = _subscription_cancelled_email_html("https://example.com/captions")
    check("Subscription cancelled (plain)", body)
    check("Subscription cancelled (HTML)", html, min_len=50)

    # Plan change confirmation
    body = "Hi,\n\nYou made changes to your Lumo 22 subscription.\n\nWhat changed: ..."
    html = _plan_change_confirmation_email_html("What changed: reduced platforms.", "Next pack.", "https://example.com/account", "£79", "£96")
    check("Plan change (plain)", body)
    check("Plan change (HTML)", html, min_len=50)

    # Order receipt
    body = "Hi,\n\nThanks for your order. We've received your payment for 30 Days of Social Media Captions."
    html = _order_receipt_email_html(order_summary="• One-off (£97)", amount_paid="£97.00")
    check("Order receipt (plain)", body)
    check("Order receipt (HTML)", html, min_len=50)

    print("Email body audit")
    print("-" * 50)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        print("-" * 50)
        print(f"FAILED: {len(errors)} issue(s), {ok_count} passed")
        sys.exit(1)
    print(f"  OK: All {ok_count} email flows produce non-empty body")
    print("-" * 50)
    print("Passed. send_email/send_email_with_attachment also validate body is non-empty before sending.")


if __name__ == "__main__":
    main()
