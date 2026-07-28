"""Pick a sensible default display currency from the visitor's country.

Outreach runs in the US, but the pricing page has always defaulted to GBP, so a US lead
lands on "£97 / £79" and has to find a currency toggle. That is friction at the worst
possible moment, and it also reads as "this is a UK company" to a US small business.

Country comes from Cloudflare's ``CF-IPCountry`` header. Cloudflare sets it at the edge
and it cannot be spoofed by the client the way ``X-Forwarded-For`` can — but it is only
present when IP Geolocation is enabled on the zone, so every path here falls back to GBP
rather than guessing.

Note this only affects the *displayed default*. An explicit ``?currency=`` parameter and
a currency the visitor has already chosen both take precedence, and Stripe still charges
in whatever currency the checkout was created with.
"""

from __future__ import annotations

from typing import Iterable, Optional

DEFAULT_CURRENCY = "gbp"

# Eurozone members plus the euro-using microstates most likely to appear in traffic.
_EUR_COUNTRIES = frozenset(
    {
        "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE", "IT", "LV",
        "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES", "AD", "MC", "SM", "VA",
    }
)

# Countries where a dollar price reads as native. Deliberately conservative: only
# places where USD is the actual currency or the standard one for online purchases.
_USD_COUNTRIES = frozenset({"US", "PR", "GU", "VI", "AS", "MP", "EC", "SV", "PA"})


def country_from_request(request) -> Optional[str]:
    """Two-letter country code from Cloudflare, or None when unavailable.

    Cloudflare sends "XX" for unknown and "T1" for Tor; both are treated as unknown.
    """
    try:
        raw = (request.headers.get("CF-IPCountry") or "").strip().upper()
    except Exception:
        return None
    if len(raw) != 2 or raw in ("XX", "T1"):
        return None
    return raw


def currency_for_country(country: Optional[str]) -> str:
    """Map a country code to a display currency, defaulting to GBP."""
    if not country:
        return DEFAULT_CURRENCY
    if country in _USD_COUNTRIES:
        return "usd"
    if country in _EUR_COUNTRIES:
        return "eur"
    return DEFAULT_CURRENCY


def resolve_default_currency(request, available_codes: Iterable[str]) -> str:
    """Default currency for this visitor, restricted to currencies actually configured.

    Falls back to GBP whenever the preferred currency has no Stripe price set up, so
    enabling geo defaulting can never surface a currency that cannot be checked out.
    """
    codes = {str(c).strip().lower() for c in (available_codes or []) if c}
    if not codes:
        return DEFAULT_CURRENCY
    preferred = currency_for_country(country_from_request(request))
    if preferred in codes:
        return preferred
    return DEFAULT_CURRENCY if DEFAULT_CURRENCY in codes else sorted(codes)[0]
