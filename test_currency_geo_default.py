#!/usr/bin/env python3
"""Default display currency from visitor region (services/request_geo.py + /captions).

US outreach was landing on GBP prices. These cover the mapping and, importantly, that
the *server-rendered* price matches — the price markup used to be a hard-coded "£97",
so a US visitor saw pounds until the pricing JS ran.
"""
import os
import re

os.environ.setdefault("DISABLE_CSRF", "1")

from services.request_geo import currency_for_country, resolve_default_currency


class _Req:
    def __init__(self, country=None):
        self.headers = {} if country is None else {"CF-IPCountry": country}


ALL = ["gbp", "usd", "eur"]


def test_country_maps_to_currency():
    assert currency_for_country("US") == "usd"
    assert currency_for_country("DE") == "eur"
    assert currency_for_country("IE") == "eur"
    assert currency_for_country("GB") == "gbp"
    assert currency_for_country("AU") == "gbp"  # no AUD price configured


def test_unknown_or_missing_country_falls_back_to_gbp():
    for country in (None, "XX", "T1", "", "USA"):
        assert resolve_default_currency(_Req(country), ALL) == "gbp"


def test_never_selects_a_currency_without_configured_prices():
    """If USD has no Stripe price, a US visitor must not be shown USD."""
    assert resolve_default_currency(_Req("US"), ["gbp"]) == "gbp"
    assert resolve_default_currency(_Req("DE"), ["gbp", "usd"]) == "gbp"
    assert resolve_default_currency(_Req("US"), ["gbp", "usd"]) == "usd"


def _get(country=None, query=""):
    from app import app

    app.config["TESTING"] = True
    headers = {"CF-IPCountry": country} if country else {}
    return app.test_client().get("/captions" + query, headers=headers)


def _prices_in(html):
    """Currency symbols appearing in the two server-rendered price elements."""
    found = []
    for el_id in ("captions-sub-price", "captions-oneoff-price"):
        m = re.search(r'id="%s"[^>]*>\s*([^\s<]+)' % el_id, html)
        if m:
            found.append(m.group(1))
    return found


def test_us_visitor_gets_dollar_prices_in_the_html():
    resp = _get("US")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    prices = _prices_in(html)
    assert prices, "price elements not found"
    assert all(p.startswith("$") for p in prices), prices


def test_uk_visitor_still_gets_pound_prices():
    html = _get("GB").get_data(as_text=True)
    prices = _prices_in(html)
    assert prices and all(p.startswith("£") for p in prices), prices


def test_no_geo_header_is_unchanged_gbp():
    """Cloudflare geolocation off, or direct origin hit — behave exactly as before."""
    html = _get(None).get_data(as_text=True)
    prices = _prices_in(html)
    assert prices and all(p.startswith("£") for p in prices), prices


def test_explicit_currency_param_overrides_geo():
    html = _get("US", "?currency=gbp").get_data(as_text=True)
    prices = _prices_in(html)
    assert prices and all(p.startswith("£") for p in prices), prices


def test_sample_order_records_the_visitor_currency():
    """A US lead's sample is stored as USD so the upgrade page opens in USD."""
    from unittest.mock import MagicMock, patch

    from app import app

    app.config["TESTING"] = True

    class _Svc:
        def __init__(self):
            self.currency = None

        def count_sample_orders_since(self, cutoff):
            return 0

        def has_sample_order_for_email(self, email):
            return False

        def create_sample_order(self, email, currency="gbp", source=None):
            self.currency = currency
            self.source = source
            return {"token": "tok-1"}

    def _start(country):
        svc = _Svc()
        with patch("services.caption_order_service.CaptionOrderService", return_value=svc), \
             patch("services.notifications.NotificationService") as notify:
            notify.return_value.send_sample_intake_link_email = MagicMock()
            resp = app.test_client().post(
                "/api/captions-sample/start",
                json={"email": "someone@gmail.com"},
                headers={"CF-IPCountry": country} if country else {},
            )
        return resp, svc

    resp, svc = _start("US")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert svc.currency == "usd"

    resp, svc = _start("GB")
    assert resp.status_code == 200
    assert svc.currency == "gbp"

    # No geolocation header -> unchanged behaviour.
    resp, svc = _start(None)
    assert resp.status_code == 200
    assert svc.currency == "gbp"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("All currency geo default tests passed.")
