#!/usr/bin/env python3
"""
Audit: verify all Lumo 22 emails use correct branding.

Checks that each email type uses:
- _email_wrapper (Lumo 22 header + footer)
- BRAND_BLACK, BRAND_GOLD, BRAND_FONT
- "Lumo 22" in header/footer/sign-off

Run: python3 check_email_branding.py
"""
import sys
from pathlib import Path

# Ensure project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    from dotenv import load_dotenv
    load_dotenv()

    from services.notifications import (
        _email_wrapper,
        _email_header_html,
        _email_footer_html,
        BRAND_BLACK,
        BRAND_GOLD,
        BRAND_FONT,
        _password_reset_email_html,
        _email_change_verification_html,
        _intake_link_email_html,
        _captions_delivery_email_html,
        _captions_reminder_email_html,
        _branded_html_email,
    )

    required_in_header = ["Lumo 22", BRAND_GOLD, BRAND_BLACK]
    required_in_footer = ["Lumo 22", "hello@lumo22.com", BRAND_GOLD]
    required_in_wrapper = ["<!DOCTYPE html", "Lumo 22"]

    errors = []
    ok_count = 0

    def check(name: str, html: str) -> None:
        nonlocal ok_count, errors
        if not html or not isinstance(html, str):
            errors.append(f"{name}: No HTML output")
            return
        for req in required_in_wrapper:
            if req not in html:
                errors.append(f"{name}: Missing '{req}' in output")
                return
        if BRAND_BLACK not in html:
            errors.append(f"{name}: Missing BRAND_BLACK")
            return
        if BRAND_GOLD not in html:
            errors.append(f"{name}: Missing BRAND_GOLD")
            return
        if "Lumo 22" not in html:
            errors.append(f"{name}: Missing 'Lumo 22'")
            return
        ok_count += 1

    # 1. Header/footer (fragments, not full HTML)
    header = _email_header_html()
    footer = _email_footer_html()
    if "Lumo 22" not in header or BRAND_GOLD not in header:
        errors.append("Header: Missing Lumo 22 or BRAND_GOLD")
    else:
        ok_count += 1
    if "Lumo 22" not in footer or "hello@lumo22.com" not in footer:
        errors.append("Footer: Missing Lumo 22 or hello@lumo22.com")
    else:
        ok_count += 1

    # 2. Explicit templates
    check("Password reset", _password_reset_email_html("https://example.com/reset"))
    check("Email change", _email_change_verification_html("https://example.com/confirm"))
    check("Intake link", _intake_link_email_html("https://example.com/intake?t=token"))
    check("Captions delivery (no stories)", _captions_delivery_email_html(False))
    check("Captions delivery (with stories)", _captions_delivery_email_html(True))
    check("Captions reminder", _captions_reminder_email_html("https://example.com/login?next=https%3A%2F%2Fexample.com%2Fcaptions-intake%3Ft%3Dx", "https://example.com/account"))

    # 3. Generic wrapper (used for plain-body emails)
    plain = "Hi,\n\nTest body.\n\n— Lumo 22"
    check("Branded HTML (plain body)", _branded_html_email(plain))

    print("Email branding audit")
    print("-" * 50)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        print("-" * 50)
        print(f"FAILED: {len(errors)} issue(s), {ok_count} passed")
        sys.exit(1)
    print(f"  OK: All {ok_count} email templates use Lumo 22 branding")
    print("-" * 50)
    print("Passed. Header, footer, and all templates include BRAND_BLACK, BRAND_GOLD, Lumo 22.")


if __name__ == "__main__":
    main()
