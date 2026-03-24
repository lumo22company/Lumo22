#!/usr/bin/env python3
"""
Verify all Captions prices: website (app.py) vs Stripe API.
Loads .env, fetches each configured Stripe Price, compares unit_amount and currency.
Run from repo root: python3 scripts/verify_all_prices.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FLASK_ENV", "development")

from dotenv import load_dotenv
load_dotenv()

# Expected: (currency, unit_amount in smallest unit, recurring bool)
# From app.CAPTIONS_DISPLAY_PRICES and api.captions_routes._CURRENCY_ADDON_AMOUNTS
EXPECTED = {
    "STRIPE_CAPTIONS_PRICE_ID": ("gbp", 9700, False),   # one-off base £97
    "STRIPE_CAPTIONS_PRICE_ID_USD": ("usd", 11900, False),
    "STRIPE_CAPTIONS_PRICE_ID_EUR": ("eur", 10900, False),
    "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID": ("gbp", 7900, True),   # sub £79/mo
    "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD": ("usd", 9900, True),
    "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR": ("eur", 8900, True),
    "STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID": ("gbp", 2900, False),  # £29
    "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID": ("gbp", 1900, True),  # £19/mo
    "STRIPE_CAPTIONS_STORIES_PRICE_ID": ("gbp", 2900, False),  # £29
    "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID": ("gbp", 1700, True),  # £17/mo
}


def main():
    import stripe
    from config import Config

    key = (Config.STRIPE_SECRET_KEY or "").strip()
    if not key:
        print("STRIPE_SECRET_KEY not set. Set it in .env to verify Stripe prices.")
        sys.exit(1)
    stripe.api_key = key

    symbols = {"gbp": "£", "usd": "$", "eur": "€"}
    ok = True
    rows = []

    for var_name, (exp_currency, exp_amount, exp_recurring) in EXPECTED.items():
        price_id = (getattr(Config, var_name, None) or os.getenv(var_name) or "").strip()
        if not price_id:
            rows.append((var_name, "—", "not set", "—", "skip"))
            continue
        try:
            price = stripe.Price.retrieve(price_id, expand=[])
        except stripe.error.InvalidRequestError as e:
            rows.append((var_name, price_id[:20] + "…", "error", str(e)[:40], "FAIL"))
            ok = False
            continue
        cur = (price.currency or "").lower()
        amount = getattr(price, "unit_amount", None) or 0
        recurring = getattr(price, "recurring", None) is not None
        match = cur == exp_currency and amount == exp_amount and recurring == exp_recurring
        exp_label = f"{symbols.get(exp_currency, exp_currency)} {exp_amount/100:.0f}"
        if exp_recurring:
            exp_label += "/mo"
        actual_label = f"{symbols.get(cur, cur)} {amount/100:.0f}" + ("/mo" if recurring else "")
        status = "OK" if match else "MISMATCH"
        if not match:
            ok = False
        rows.append((var_name, price_id[:24], exp_label, actual_label, status))

    # Print report
    print("\n" + "=" * 80)
    print("Lumo 22 — Price verification (website vs Stripe)")
    print("=" * 80)
    print(f"{'Variable':<50} {'Expected':<18} {'Stripe':<18} {'Status':<10}")
    print("-" * 80)
    for var_name, _pid, exp_label, actual_label, status in rows:
        print(f"{var_name:<50} {exp_label:<18} {actual_label:<18} {status:<10}")
    print("=" * 80)
    if ok:
        print("All configured prices match expected amounts.")
    else:
        print("One or more prices are missing or do not match. Fix Stripe or update app CAPTIONS_DISPLAY_PRICES.")
        sys.exit(1)


if __name__ == "__main__":
    main()
