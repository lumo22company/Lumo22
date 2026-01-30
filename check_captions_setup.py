#!/usr/bin/env python3
"""
30 Days Captions — setup checker.
Run from project root: python check_captions_setup.py

Checks env vars and (if Supabase is set) whether caption_orders table exists.
Does NOT check Stripe, SendGrid, or OpenAI — you must set those up yourself.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def mask(s, show=8):
    if not s or len(s) < show:
        return "***"
    return s[:show] + "..." if len(s) > show else s

def main():
    print("=" * 60)
    print("30 DAYS CAPTIONS — SETUP CHECK")
    print("=" * 60)
    print()

    required = {
        "CAPTIONS_PAYMENT_LINK": "Stripe payment link (from Step 2)",
        "STRIPE_WEBHOOK_SECRET": "Stripe webhook signing secret (from Step 3)",
        "BASE_URL": "Your site URL, no trailing slash (e.g. https://lumo22.com)",
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_KEY": "Supabase anon key",
        "SENDGRID_API_KEY": "SendGrid API key",
        "FROM_EMAIL": "Email address emails are sent from",
        "OPENAI_API_KEY": "OpenAI API key for caption generation",
    }

    ok = []
    missing = []

    placeholders = (
        "your-", "xxxx", "yourdomain.com", "example.com",
        "whsec_your_webhook_secret", "buy.stripe.com/your",
    )

    for key, desc in required.items():
        val = (os.getenv(key) or "").strip()
        is_placeholder = any(p in val.lower() for p in placeholders) if val else True
        if not val or is_placeholder:
            missing.append((key, desc))
        else:
            if key == "OPENAI_API_KEY":
                ok.append((key, mask(val, 7)))
            elif key == "SUPABASE_KEY" or key == "SENDGRID_API_KEY" or key == "STRIPE_WEBHOOK_SECRET":
                ok.append((key, mask(val, 8)))
            else:
                ok.append((key, val[:50] + "..." if len(val) > 50 else val))

    print("Configured:")
    for k, v in ok:
        print(f"  OK  {k}: {v}")
    print()

    if missing:
        print("Missing or still placeholder:")
        for k, desc in missing:
            print(f"  X   {k}")
            print(f"      -> {desc}")
        print()
        print("Add these to your .env file (see .env.example).")
        print("Step-by-step: products/30-days-social-captions/SETUP_STEP_BY_STEP_ASSUME_NOTHING.md")
        print()
        sys.exit(1)

    # Optional: check Supabase table exists
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if url and key and "your-project" not in url and "your-supabase" not in key:
        try:
            from supabase import create_client
            client = create_client(url, key)
            r = client.table("caption_orders").select("id").limit(1).execute()
            print("Database: caption_orders table exists and is readable.")
        except Exception as e:
            print("Database: could not read caption_orders.")
            print("  -> Run the SQL in database_caption_orders.sql in Supabase SQL Editor.")
            print(f"  (Error: {e})")
    else:
        print("Database: skipped (Supabase not configured or placeholder).")

    print()
    print("Env and (if checked) database look good.")
    print("You still need to:")
    print("  1. Create Stripe product + payment link + webhook (Steps 2–3 in the guide).")
    print("  2. Paste the payment link and webhook secret into .env (you have values set).")
    print("  3. Run or deploy the app; set BASE_URL to your live site.")
    print("  4. Test: pay with Stripe test card -> get email -> fill intake -> get captions email.")
    print()

if __name__ == "__main__":
    main()
