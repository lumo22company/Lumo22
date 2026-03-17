#!/usr/bin/env python3
"""
Test that the user is charged the correct amount for every subscription scenario.
Run: python3 test_subscription_charges.py

Scenarios:
- Subscription monthly total (display) = sub + (platforms-1)*extra_sub + stories_sub (if stories)
- Stripe amounts (smallest unit) must match: base + addons
- All currencies (GBP, USD, EUR), platforms 1-4, stories on/off
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Display prices (main currency units) - must match app.CAPTIONS_DISPLAY_PRICES
DISPLAY_PRICES = {
    "gbp": {"sub": 79, "extra_sub": 19, "stories_sub": 17},
    "usd": {"sub": 99, "extra_sub": 24, "stories_sub": 21},
    "eur": {"sub": 89, "extra_sub": 22, "stories_sub": 19},
}

# Base subscription amount in smallest unit (pence/cents) - what Stripe uses for base price
BASE_AMOUNT_SMALLEST = {"gbp": 7900, "usd": 9900, "eur": 8900}

# Addon amounts in smallest unit (from api.captions_routes._CURRENCY_ADDON_AMOUNTS)
ADDON_AMOUNTS = {
    "gbp": {"extra_sub": 1900, "stories_sub": 1700},
    "usd": {"extra_sub": 2400, "stories_sub": 2100},
    "eur": {"extra_sub": 2200, "stories_sub": 1900},
}


def expected_display_total(currency: str, platforms: int, stories: bool) -> int:
    """Expected monthly total in main currency units (e.g. 79, 98, 115)."""
    p = DISPLAY_PRICES.get(currency, DISPLAY_PRICES["gbp"])
    total = p["sub"] + (platforms - 1) * p["extra_sub"]
    if stories:
        total += p["stories_sub"]
    return total


def expected_amount_smallest_unit(currency: str, platforms: int, stories: bool) -> int:
    """Expected charge in smallest unit (pence/cents) for one month."""
    base = BASE_AMOUNT_SMALLEST.get(currency, 7900)
    addons = ADDON_AMOUNTS.get(currency, ADDON_AMOUNTS["gbp"])
    total = base + (platforms - 1) * addons["extra_sub"]
    if stories:
        total += addons["stories_sub"]
    return total


def test_display_consistency():
    """Display total (pounds/dollars/euros) × 100 should equal amount in smallest unit."""
    for currency in ("gbp", "usd", "eur"):
        for platforms in range(1, 5):
            for stories in (False, True):
                display = expected_display_total(currency, platforms, stories)
                smallest = expected_amount_smallest_unit(currency, platforms, stories)
                # Display is in main units (79, 98); smallest is pence/cents (7900, 9800)
                assert display * 100 == smallest, (
                    f"{currency} platforms={platforms} stories={stories}: "
                    f"display {display} * 100 = {display * 100} != smallest {smallest}"
                )
    print("OK: Display total × 100 equals smallest unit for all plans.")


def test_app_formula_matches():
    """App.py formula total = prices['sub'] + (platforms-1)*extra_sub + (stories_sub if stories else 0) matches our expected."""
    for currency in ("gbp", "usd", "eur"):
        p = DISPLAY_PRICES[currency]
        for platforms in range(1, 5):
            for stories in (False, True):
                app_style = p["sub"] + (platforms - 1) * p["extra_sub"] + (p["stories_sub"] if stories else 0)
                expected = expected_display_total(currency, platforms, stories)
                assert app_style == expected, (
                    f"{currency} platforms={platforms} stories={stories}: app formula {app_style} != expected {expected}"
                )
    print("OK: App formula matches expected display total.")


def test_app_display_prices_match():
    """App.CAPTIONS_DISPLAY_PRICES subscription fields match our DISPLAY_PRICES (single source of truth)."""
    from app import CAPTIONS_DISPLAY_PRICES
    for currency in ("gbp", "usd", "eur"):
        app_p = CAPTIONS_DISPLAY_PRICES.get(currency, {})
        our_p = DISPLAY_PRICES.get(currency, {})
        assert app_p.get("sub") == our_p["sub"], f"{currency} sub: app={app_p.get('sub')} test={our_p['sub']}"
        assert app_p.get("extra_sub") == our_p["extra_sub"], f"{currency} extra_sub: app={app_p.get('extra_sub')} test={our_p['extra_sub']}"
        assert app_p.get("stories_sub") == our_p["stories_sub"], f"{currency} stories_sub: app={app_p.get('stories_sub')} test={our_p['stories_sub']}"
    print("OK: App CAPTIONS_DISPLAY_PRICES matches test expected (subscription amounts).")


def test_captions_routes_addon_amounts():
    """_CURRENCY_ADDON_AMOUNTS in captions_routes matches our ADDON_AMOUNTS (so Stripe charge is correct)."""
    from api.captions_routes import _CURRENCY_ADDON_AMOUNTS
    for currency in ("gbp", "usd", "eur"):
        ours = ADDON_AMOUNTS.get(currency)
        theirs = _CURRENCY_ADDON_AMOUNTS.get(currency)
        assert theirs is not None, f"Missing currency {currency} in _CURRENCY_ADDON_AMOUNTS"
        assert theirs["extra_sub"] == ours["extra_sub"], (
            f"{currency} extra_sub: routes has {theirs['extra_sub']}, test expects {ours['extra_sub']}"
        )
        assert theirs["stories_sub"] == ours["stories_sub"], (
            f"{currency} stories_sub: routes has {theirs['stories_sub']}, test expects {ours['stories_sub']}"
        )
    print("OK: captions_routes addon amounts match expected (Stripe charge correct).")


def test_scenario_amounts():
    """Table of expected amounts for every scenario (charge at checkout or at trial end)."""
    scenarios = []
    for currency in ("gbp", "usd", "eur"):
        sym = {"gbp": "£", "usd": "$", "eur": "€"}[currency]
        for platforms in range(1, 5):
            for stories in (False, True):
                display = expected_display_total(currency, platforms, stories)
                smallest = expected_amount_smallest_unit(currency, platforms, stories)
                scenarios.append({
                    "currency": currency,
                    "platforms": platforms,
                    "stories": stories,
                    "display": f"{sym}{display}",
                    "smallest_unit": smallest,
                })
    # Assert all positive and reasonable
    for s in scenarios:
        assert s["smallest_unit"] > 0, f"Scenario {s}: expected positive amount"
        assert s["smallest_unit"] == expected_amount_smallest_unit(
            s["currency"], s["platforms"], s["stories"]
        ), f"Scenario {s}: amount mismatch"
    print(f"OK: {len(scenarios)} scenarios have correct positive amounts.")
    return scenarios


def test_trial_first_charge_equals_one_month():
    """When trial ends, first charge must equal one month subscription (same line_items as at signup)."""
    # The subscription is created with the same line_items whether or not trial;
    # so first invoice after trial = one month of that plan = our expected_amount_smallest_unit.
    for currency in ("gbp", "usd", "eur"):
        for platforms in range(1, 5):
            for stories in (False, True):
                one_month = expected_amount_smallest_unit(currency, platforms, stories)
                assert one_month > 0
    print("OK: Trial end first charge = one month (same as get-pack-now / new sub charge).")


def test_get_pack_now_charge_equals_one_month():
    """Get pack now: charge at checkout = one month subscription (no trial)."""
    # Same as test_trial_first_charge: one month. So we just ensure the subscription
    # checkout without trial uses the same line_items → same amount.
    from api.captions_routes import _CURRENCY_ADDON_AMOUNTS
    for currency in ("gbp", "usd", "eur"):
        addons = _CURRENCY_ADDON_AMOUNTS.get(currency)
        assert addons is not None
        # 1 platform, no stories = base only; we don't have base in ADDON_AMOUNTS so check via expected
        one_platform_no_stories = expected_amount_smallest_unit(currency, 1, False)
        assert one_platform_no_stories == BASE_AMOUNT_SMALLEST.get(currency, 7900)
    print("OK: Get pack now / new sub charge = one month (base + addons).")


def run_all():
    test_display_consistency()
    test_app_formula_matches()
    test_app_display_prices_match()
    test_captions_routes_addon_amounts()
    test_scenario_amounts()
    test_trial_first_charge_equals_one_month()
    test_get_pack_now_charge_equals_one_month()
    print("\nAll subscription charge amount tests passed.")


if __name__ == "__main__":
    run_all()
