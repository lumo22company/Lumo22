#!/usr/bin/env python3
"""
Pre-launch verification: checks .env config and optionally pings live endpoints.
Run: python3 scripts/pre_launch_check.py
Or: python3 scripts/pre_launch_check.py --live   (also checks deployed site)
"""
import os
import sys
from pathlib import Path

# Load .env from project root
root = Path(__file__).resolve().parent.parent
env_file = root / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

REQUIRED = [
    "OPENAI_API_KEY",
    "SENDGRID_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "FROM_EMAIL",
    "BASE_URL",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
]

# Captions is the only active product
PAYMENT_LINKS = [
    "CAPTIONS_PAYMENT_LINK",
]

OPTIONAL = [
    "STRIPE_CAPTIONS_PRICE_ID",
    "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID",
    "CAPTIONS_DELIVER_TEST_SECRET",
]


def mask(val):
    if not val or len(val) < 8:
        return "(not set)" if not val else "***"
    return val[:4] + "…" + val[-4:] if len(val) > 8 else "***"


def check_env():
    ok = True
    print("=" * 50)
    print("PRE-LAUNCH CHECK")
    print("=" * 50)
    print()

    # Required vars
    print("Required (.env):")
    for key in REQUIRED:
        val = os.getenv(key, "").strip()
        status = "✓" if val and "YOUR" not in val.upper() and "PASSWORD" not in val.upper() else "✗"
        if status == "✗":
            ok = False
        hint = mask(val) if val else "(missing)"
        print(f"  {status} {key}: {hint}")
    print()

    # Payment (Captions)
    print("Captions payment:")
    captions_link = os.getenv("CAPTIONS_PAYMENT_LINK", "").strip()
    captions_price = os.getenv("STRIPE_CAPTIONS_PRICE_ID", "").strip()
    has_link = captions_link and "buy.stripe.com" in captions_link
    has_price = captions_price and captions_price.startswith("price_")
    status = "✓" if has_link or has_price else "✗"
    if status == "✗":
        ok = False
    print(f"  {status} CAPTIONS_PAYMENT_LINK or STRIPE_CAPTIONS_PRICE_ID (need one)")
    print()

    # BASE_URL format
    base = os.getenv("BASE_URL", "").strip().rstrip("/")
    if base:
        if base.endswith("/"):
            print("  ⚠ BASE_URL should not have trailing slash")
            ok = False
        if not base.startswith("https://"):
            print("  ⚠ BASE_URL should use https:// in production")
        print(f"  Base URL: {base}")
    print()

    # Optional
    print("Optional:")
    for key in OPTIONAL:
        val = os.getenv(key, "").strip()
        status = "✓" if val else "-"
        print(f"  {status} {key}")
    print()

    return ok


def _try_url(url):
    """Fetch URL, return status code or error string."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Lumo22-PreLaunch"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.getcode()
    except Exception as e:
        return f"Error: {str(e)[:50]}"


def _www_alt(base):
    """If base is apex (no www), return www variant for same domain."""
    base = base.rstrip("/")
    if not base or "localhost" in base:
        return None
    if "://www." in base:
        return None
    try:
        from urllib.parse import urlparse
        p = urlparse(base)
        if p.hostname and "." in p.hostname and not p.hostname.startswith("www."):
            return f"{p.scheme}://www.{p.hostname}"
    except Exception:
        pass
    return None


def check_live(base_url):
    """Ping key endpoints on live site. If apex fails, try www variant."""
    base = base_url.rstrip("/")
    endpoints = [
        ("/", 200),
        ("/captions", 200),
        ("/terms", 200),
        ("/captions-thank-you", 200),
        ("/captions-pack-sooner-thank-you", 200),
    ]
    print("Live site check (BASE_URL=" + base + "):")
    all_ok = True
    used_www_fallback = False
    www_url = _www_alt(base)
    for path, expect in endpoints:
        url = base + path
        got = _try_url(url)
        if got != expect:
            # Try www variant (apex often 404s on subpaths with GoDaddy forwarding)
            if www_url:
                alt_got = _try_url(www_url + path)
                if alt_got == expect:
                    got = expect
                    used_www_fallback = True
                    if path == "/":
                        print(f"  ✓ {path} → 200 (via {www_url})")
                    else:
                        print(f"  ✓ {path} → 200 (use BASE_URL={www_url})")
                    continue
        status = "✓" if got == expect else "✗"
        if got != expect:
            all_ok = False
        print(f"  {status} {path} → {got}")
    if not all_ok and www_url:
        print(f"\n  Tip: Set BASE_URL={www_url} (see GODADDY_DNS_RAILWAY.md)")
    elif used_www_fallback:
        print(f"\n  Tip: Set BASE_URL={www_url} in .env and Railway so links use the canonical domain")
    return all_ok


def main():
    check_live_flag = "--live" in sys.argv
    env_ok = check_env()
    live_ok = True
    if check_live_flag:
        base = os.getenv("BASE_URL", "").strip().rstrip("/")
        if base and base != "http://localhost:5001":
            live_ok = check_live(base)
        else:
            print("Live check skipped (BASE_URL is localhost or not set)")
    else:
        print("Tip: Run with --live to also check deployed site")

    print()
    print("=" * 50)
    if env_ok and (not check_live_flag or live_ok):
        print("✓ Pre-launch check passed")
    else:
        print("✗ Some checks failed — fix the items above")
        sys.exit(1)


if __name__ == "__main__":
    main()
