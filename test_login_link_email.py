#!/usr/bin/env python3
"""
Build and optionally send the login-link email so you can verify the URL is not blank.
Uses the same URL logic as the app (fallback base, sanitization). Uses .env.

Usage:
  python3 test_login_link_email.py your@email.com
      → Prints the URL that would be sent (no email). Use to confirm URL is built.
  python3 test_login_link_email.py your@email.com --send
      → Sends the email. Check your inbox to confirm the link appears (link may not work if app restarted).
  python3 test_login_link_email.py --show-url-only
      → Builds and prints the login URL using BASE_URL from .env (no DB lookup). Use to verify URL is never blank.
"""
import sys
import os
import secrets

from dotenv import load_dotenv
load_dotenv()


def build_login_link_url(customer_id: str, customer_email: str, base_url_from_config: str):
    """Mirror app.py URL building so we can test it standalone."""
    fallback_base = "https://lumo-22-production.up.railway.app"
    raw = (base_url_from_config or "").strip() or fallback_base
    base = "".join(c for c in raw if ord(c) >= 32 and c not in "\n\r\t").rstrip("/") or fallback_base
    if not base.startswith("http"):
        base = "https://" + base.lstrip("/")
    # Token for display/send (script doesn't register it with the app, so link may not work when clicked)
    login_token = secrets.token_urlsafe(32)
    account_url = (base.rstrip("/") + "/account?login_token=" + login_token)
    account_url = "".join(c for c in account_url if ord(c) >= 32 and c not in "\n\r\t")
    if not account_url.startswith("http"):
        account_url = fallback_base.rstrip("/") + "/account?login_token=" + login_token
    return account_url


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    do_send = "--send" in flags
    show_url_only = "--show-url-only" in flags

    if show_url_only:
        from config import Config
        print("--- Login link URL (show-url-only, no DB) ---")
        base_from_config = getattr(Config, "BASE_URL", None) or ""
        print(f"  BASE_URL (config): {repr(Config.BASE_URL)}")
        account_url = build_login_link_url("00000000-0000-0000-0000-000000000000", "test@example.com", base_from_config)
        print(f"  Built account URL (length={len(account_url)}):")
        print(f"    {account_url}")
        print()
        print("  Plain text snippet that would be in the email:")
        print("  ---")
        print("  Click the link below to open your account (link works once, expires in 2 minutes):")
        print()
        print(f"  {account_url}")
        print()
        print("  ---")
        sys.exit(0)

    if len(args) < 1:
        print("Usage: python3 test_login_link_email.py your@email.com [--send]")
        print("       python3 test_login_link_email.py --show-url-only")
        sys.exit(1)
    email = args[0].strip().lower()
    if "@" not in email:
        print("ERROR: Provide a valid email address.")
        sys.exit(1)

    from config import Config
    from services.customer_auth_service import CustomerAuthService
    from services.notifications import NotificationService

    print("--- Login link email test ---")
    print(f"  Email: {email}")
    print(f"  BASE_URL (config): {repr(Config.BASE_URL)}")
    print(f"  SENDGRID_API_KEY set: {bool(Config.SENDGRID_API_KEY)}")
    print()

    svc = CustomerAuthService()
    customer = svc.get_by_email(email)
    if not customer:
        print("  No customer found with this email. The app would not send an email.")
        print("  Sign up or use an email that already has an account.")
        print("  To see the URL that would be built anyway, run: python3 test_login_link_email.py --show-url-only")
        sys.exit(1)

    base_from_config = getattr(Config, "BASE_URL", None) or ""
    account_url = build_login_link_url(
        str(customer["id"]),
        customer["email"],
        base_from_config,
    )

    print("  Customer found.")
    print(f"  Built account URL (length={len(account_url)}):")
    print(f"    {account_url}")
    print()
    if not account_url.startswith("http"):
        print("  ERROR: URL does not start with http — link would be blank in email.")
        sys.exit(1)
    print("  Plain text snippet that would be in the email:")
    print("  ---")
    print("  Click the link below to open your account (link works once, expires in 2 minutes):")
    print()
    print(f"  {account_url}")
    print()
    print("  If the link doesn't work, copy and paste the link above into your browser.")
    print("  ---")
    print()

    if do_send:
        print("  Sending email via NotificationService.send_login_link_email(...)")
        notif = NotificationService()
        sent = notif.send_login_link_email(email, account_url)
        if sent:
            print("  SUCCESS: Email sent. Check inbox/spam and confirm the link appears.")
        else:
            print("  FAILED: send_login_link_email returned False. Check [SendGrid] output above.")
        sys.exit(0 if sent else 1)

    print("  (No email sent. Run with --send to send the email and verify the link in your client.)")


if __name__ == "__main__":
    main()
