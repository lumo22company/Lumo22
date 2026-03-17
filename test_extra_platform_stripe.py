"""
Test that Extra platform Stripe product and prices are configured correctly
(name "Extra platform", expected description). Requires STRIPE_SECRET_KEY and
the two STRIPE_CAPTIONS_EXTRA_PLATFORM_* price IDs in .env.
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()

EXPECTED_NAME = "Extra platform"
EXPECTED_DESCRIPTION = "Extra platform for your 30 Days Captions pack. Content delivered with your next pack."


def test_extra_platform_stripe_setup():
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    price_id = os.getenv("STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID", "").strip()
    sub_price_id = os.getenv("STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", "").strip()

    assert stripe_key, "STRIPE_SECRET_KEY not set"
    assert price_id, "STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID not set"
    assert sub_price_id, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID not set"

    import stripe
    stripe.api_key = stripe_key

    for label, pid in [("One-off", price_id), ("Subscription", sub_price_id)]:
        price = stripe.Price.retrieve(pid, expand=["product"])
        product = price.get("product")
        if isinstance(product, str):
            product = stripe.Product.retrieve(product)
        assert product.get("name") == EXPECTED_NAME, (
            f"{label}: product name should be '{EXPECTED_NAME}', got '{product.get('name')}'"
        )
        assert (product.get("description") or "").strip() == EXPECTED_DESCRIPTION, (
            f"{label}: product description mismatch"
        )


if __name__ == "__main__":
    try:
        test_extra_platform_stripe_setup()
        print("PASS: Extra platform Stripe setup OK")
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
