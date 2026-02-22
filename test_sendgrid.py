#!/usr/bin/env python3
"""
Send one test email via SendGrid using your .env config.
Usage: python3 test_sendgrid.py your@email.com
"""
import sys
import os

# Load .env before importing app code
from dotenv import load_dotenv
load_dotenv()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_sendgrid.py your@email.com")
        sys.exit(1)
    to_email = sys.argv[1].strip()

    from config import Config
    from services.notifications import NotificationService

    if not Config.SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY is not set in .env")
        sys.exit(1)
    if not Config.FROM_EMAIL:
        print("ERROR: FROM_EMAIL is not set in .env")
        sys.exit(1)

    print(f"Sending test email from {Config.FROM_EMAIL} to {to_email} ...")
    notif = NotificationService()
    ok = notif.send_email(
        to_email,
        subject="Lumo 22 — SendGrid test",
        body="This is a test email from your Lumo 22 app. If you received this, SendGrid is working.",
    )
    if ok:
        print("SUCCESS: Email sent. Check your inbox (and spam).")
    else:
        print("FAILED: Email was not sent. Check the error above or SENDGRID_VERIFY_EMAILS.md")

if __name__ == "__main__":
    main()
