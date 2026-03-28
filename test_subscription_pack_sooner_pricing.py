"""
Regression: "Get my pack sooner" modal amount (customer_dashboard template) must match
billing_routes._subscription_monthly_price for the same order shape (platforms_count, stories, currency).

Also ensures CAPTIONS_DISPLAY_PRICES (app) stays aligned with billing display prices.
"""
import pytest

from api.billing_routes import _subscription_monthly_price
from app import CAPTIONS_DISPLAY_PRICES


def _template_pack_sooner_total(currency: str, platforms: int, include_stories: bool) -> int:
    """Mirror templates/customer_dashboard.html _gps_total calculation."""
    cur = (currency or "gbp").lower()
    p = CAPTIONS_DISPLAY_PRICES.get(cur, CAPTIONS_DISPLAY_PRICES["gbp"])
    n = max(1, int(platforms))
    total = p.get("sub", 79) + (n - 1) * p.get("extra_sub", 19)
    if include_stories:
        total += p.get("stories_sub", 17)
    return int(total)


@pytest.mark.parametrize("currency", ["gbp", "usd", "eur"])
@pytest.mark.parametrize("platforms", [1, 2, 3, 4])
@pytest.mark.parametrize("include_stories", [False, True])
def test_get_pack_sooner_display_matches_billing_monthly_price(currency, platforms, include_stories):
    sym, amt = _subscription_monthly_price(currency, platforms, include_stories)
    tpl = _template_pack_sooner_total(currency, platforms, include_stories)
    assert amt == tpl, f"{currency} p={platforms} stories={include_stories}: billing {amt} vs template {tpl}"
    prices = CAPTIONS_DISPLAY_PRICES[currency]
    assert sym == prices["symbol"]


def test_billing_display_prices_match_app_captions_prices():
    """_subscription_monthly_price uses _DISPLAY_PRICES in billing_routes — keep in sync with app."""
    from api.billing_routes import _DISPLAY_PRICES

    for cur in ("gbp", "usd", "eur"):
        assert _DISPLAY_PRICES[cur]["sub"] == CAPTIONS_DISPLAY_PRICES[cur]["sub"]
        assert _DISPLAY_PRICES[cur]["extra_sub"] == CAPTIONS_DISPLAY_PRICES[cur]["extra_sub"]
        assert _DISPLAY_PRICES[cur]["stories_sub"] == CAPTIONS_DISPLAY_PRICES[cur]["stories_sub"]
        assert _DISPLAY_PRICES[cur]["symbol"] == CAPTIONS_DISPLAY_PRICES[cur]["symbol"]
