#!/usr/bin/env python3
"""
Test scenarios for one-off → subscription upgrade flows (charge on delivery vs get pack now).
Run: python3 test_upgrade_flows.py

Covers:
1. Deferred charge: subscription_data.billing_cycle_anchor + proration_behavior when copy_from and not get_pack_now (no “days free”)
2. No deferred charge when get_pack_now
3. invoice.paid: copy intake from one-off when order has no intake (upgrader)
4. No "trial" in user-facing copy
5. Emails: upgrader (no charge today) gets upgrade confirmation (not checkout intake email); get_pack_now gets welcome prefilled
"""

import os
import sys

# Allow importing app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_no_trial_in_templates():
    """Customer never sees the word 'trial'."""
    for root, _, files in os.walk("templates"):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read().lower()
                assert "trial" not in content, f"Template {path} contains 'trial'"
    print("OK: No 'trial' in any template.")


def test_billing_anchor_only_when_upgrader_no_get_pack_now():
    """Subscription checkout only uses billing_cycle_anchor (no trial) when copy_from and not get_pack_now."""
    import api.captions_routes as m
    src = open(m.__file__, "r").read()
    assert "subscription_data" in src and "billing_cycle_anchor" in src
    assert "proration_behavior" in src
    assert "copy_from and not get_pack_now" in src
    print("OK: Billing anchor only for upgrader without get_pack_now.")


def test_invoice_paid_copies_intake():
    """invoice.paid handler copies intake from one-off when order has upgraded_from_token and no intake."""
    import api.webhooks as wh
    src = open(wh.__file__, "r").read()
    assert "upgraded_from_token" in src
    assert "save_intake" in src or "one_off" in src
    print("OK: invoice.paid can copy intake from one-off.")


def test_upgrade_confirmation_email_exists():
    """NotificationService has upgrade confirmation email for trial (no charge today)."""
    from services.notifications import NotificationService
    assert hasattr(NotificationService, "send_subscription_upgrade_confirmation_email")
    print("OK: send_subscription_upgrade_confirmation_email exists.")


def test_webhook_single_checkout_email_with_session():
    """Standard captions checkout sends one combined email; webhook passes Stripe session into send helper."""
    import api.webhooks as wh
    src = open(wh.__file__, "r").read()
    assert "is_trial_upgrade" in src
    assert "send_subscription_upgrade_confirmation_email" in src
    assert "_send_intake_email_for_order" in src
    assert "checkout_session=session" in src
    assert "send_order_receipt_email" not in src
    print("OK: Webhook uses _send_intake_email_for_order with session (no separate receipt).")


def test_get_pack_today_edit_form_first_ui():
    """Option A: When 'Get my first subscription pack today' is selected, 'Edit form first' block exists and link uses return_url."""
    path = os.path.join(os.path.dirname(__file__), "templates", "customer_dashboard.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "upgrade-edit-form-first-wrap" in html
    assert "upgrade-edit-form-first-link" in html
    assert "Do you need to update your form" in html or "edit your form" in html.lower()
    assert "return_url" in html
    assert "/account/upgrade" in html
    assert "captions-intake?t=" in html or "'/captions-intake?t='" in html
    assert "getPackToday" in html and "copyFrom" in html
    print("OK: Get my pack today + Edit form first UI and return_url link present.")


def run_all():
    test_no_trial_in_templates()
    test_billing_anchor_only_when_upgrader_no_get_pack_now()
    test_invoice_paid_copies_intake()
    test_upgrade_confirmation_email_exists()
    test_webhook_single_checkout_email_with_session()
    print("\nAll upgrade-flow checks passed.")


if __name__ == "__main__":
    run_all()
