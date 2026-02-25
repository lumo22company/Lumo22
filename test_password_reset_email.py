#!/usr/bin/env python3
"""
Test the full password-reset flow: look up customer, create token, send email.
Use this to verify you receive the reset email. Uses .env (Supabase, SendGrid, BASE_URL).

Usage:
  python3 test_password_reset_email.py your@email.com
  python3 test_password_reset_email.py your@email.com --send-anyway   # send test email even if no customer (tests SendGrid)
  python3 test_password_reset_email.py your@email.com --check-only    # only check if email exists in DB
"""
import sys
import os

from dotenv import load_dotenv
load_dotenv()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_password_reset_email.py your@email.com [--send-anyway|--check-only]")
        sys.exit(1)
    args = [a for a in sys.argv[1:] if a.startswith("--")]
    email = sys.argv[1].strip().lower()
    if "@" not in email:
        print("ERROR: Provide a valid email address.")
        sys.exit(1)
    send_anyway = "--send-anyway" in args
    check_only = "--check-only" in args

    from config import Config
    from services.customer_auth_service import CustomerAuthService
    from services.notifications import NotificationService

    print("--- Password reset email test ---")
    print(f"  Email: {email}")
    print(f"  FROM_EMAIL (config): {Config.FROM_EMAIL!r}")
    print(f"  BASE_URL: {Config.BASE_URL or '(not set)'}")
    print(f"  SENDGRID_API_KEY set: {bool(Config.SENDGRID_API_KEY)}")
    print()

    svc = CustomerAuthService()
    customer = svc.get_by_email(email)
    if not customer:
        if check_only:
            print("  RESULT: No customer found with this email. They would not receive a reset email.")
            sys.exit(0)
        if not send_anyway:
            print("  RESULT: No customer found with this email. The app would still return 'success' but send no email.")
            print("  Fix: Sign up with this email first, or use an email that already has an account.")
            print("  To test SendGrid anyway, run: python3 test_password_reset_email.py " + email + " --send-anyway")
            sys.exit(1)
        print("  No customer found; --send-anyway: sending a test email to verify SendGrid delivery.")
        notif = NotificationService()
        sent = notif.send_email(
            email,
            "Lumo 22 — Password reset test (no account)",
            "This is a SendGrid test. If you got this, SendGrid is working. Your email is not in our system yet — sign up at the site to get a real reset link.",
        )
        if sent:
            print("  SUCCESS: Test email sent. Check inbox/spam. If you received it, SendGrid works; the issue is the email not being in the customers table.")
        else:
            print("  FAILED: SendGrid did not send. Check the [SendGrid] messages above.")
        sys.exit(0 if sent else 1)

    print("  Customer found. Creating reset token ...")
    ok, token = svc.request_password_reset(email)
    if not ok:
        print(f"  ERROR creating token: {token}")
        sys.exit(1)
    if not token:
        print("  ERROR: Token was None unexpectedly.")
        sys.exit(1)

    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http"):
        base = "https://" + base
    reset_url = f"{base}/reset-password?token={token}" if base else "BASE_URL not set"
    print(f"  Reset URL: {reset_url}")
    print()

    subject = "Reset your Lumo 22 password (test)"
    body = f"""Hi,

You requested a password reset for your Lumo 22 account.

Click the link below to set a new password (link expires in 1 hour):

{reset_url}

If you didn't request this, you can ignore this email. Your password will stay the same.

— Lumo 22
"""
    notif = NotificationService()
    sent = notif.send_email(email, subject, body)
    if sent:
        print("  SUCCESS: Email sent. Check your inbox (and spam) for the reset link.")
    else:
        print("  FAILED: SendGrid did not send the email. Check the [SendGrid] messages above.")
        print("  Common fixes: set SENDGRID_API_KEY, verify FROM_EMAIL (e.g. noreply@lumo22.com) in SendGrid.")
        sys.exit(1)

if __name__ == "__main__":
    main()
