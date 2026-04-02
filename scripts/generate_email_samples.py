#!/usr/bin/env python3
"""
Generate sample email HTML files so you can preview how they look.
Run: python3 scripts/generate_email_samples.py
Creates email_samples/ — open index.html in your browser.
No SendGrid required.
"""
import os
import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

def main():
    from dotenv import load_dotenv
    load_dotenv()

    # Import after chdir so config loads correctly
    from services.notifications import (
        _branded_html_email,
        _password_reset_email_html,
        _email_change_verification_html,
        _intake_link_email_html,
        _captions_delivery_email_html,
        _captions_reminder_email_html,
        _welcome_and_verify_email_html,
        _order_receipt_email_html,
        _plan_change_confirmation_email_html,
        _subscription_cancelled_email_html,
    )

    out_dir = project_root / "email_samples"
    out_dir.mkdir(exist_ok=True)
    index_lines = []

    samples = []

    # 1. Form link email (after captions purchase) — uses production template
    intake_url = "https://www.lumo22.com/captions-intake?t=sample-token"
    samples.append(("intake.html", "Order confirmed + form link (after captions checkout)", _intake_link_email_html(intake_url, "• One-off (£97)\n• 1 platform", is_subscription=False)))

    # 2. Delivery email — uses production template
    samples.append(("delivery.html", "Delivery email (with attachment)", _captions_delivery_email_html(has_stories=False, has_subscription=False)))
    samples.append(("delivery_stories.html", "Delivery email (with Stories)", _captions_delivery_email_html(has_stories=True, has_subscription=False)))
    samples.append(("delivery_subscription.html", "Delivery email (subscription - with delete note)", _captions_delivery_email_html(has_stories=False, has_subscription=True)))

    # 3. Caption reminder (subscribers log in first, then redirect to form)
    from urllib.parse import quote
    account_url = "https://www.lumo22.com/account"
    login_url = "https://www.lumo22.com/login?next=" + quote(intake_url, safe="")
    samples.append(("reminder.html", "Pre-pack reminder", _captions_reminder_email_html(login_url, account_url)))

    # 4. Password reset
    samples.append(("password_reset.html", "Password reset", _password_reset_email_html("https://www.lumo22.com/reset-password?token=sample-token")))

    # 5. Email change verification
    samples.append(("email_change.html", "Email change verification", _email_change_verification_html("https://www.lumo22.com/change-email-confirm?token=sample-token")))

    # 6. Welcome + email verification (signup)
    samples.append(("welcome_verify.html", "Welcome + email verification (signup)", _welcome_and_verify_email_html("https://www.lumo22.com/verify-email?token=sample-token")))

    # 7. Order receipt (thanks for your order) — with product summary and amount
    samples.append((
        "order_receipt.html",
        "Order receipt (thanks for your order)",
        _order_receipt_email_html(
            order={
                "platforms_count": 2,
                "stripe_subscription_id": None,
                "include_stories": False,
                "selected_platforms": "Instagram, LinkedIn",
                "currency": "gbp",
            },
            amount_paid="£126.00",
            amount_total_minor=12600,
            currency="gbp",
        ),
    ))

    # 8. Plan change confirmation (upgrade/add-on)
    samples.append((
        "plan_change_upgrade.html",
        "Plan change confirmation (upgrade/add Stories/add platforms)",
        _plan_change_confirmation_email_html(
            "What changed: 30 Days Story Ideas has been added to your subscription.",
            "Stories will be included in your next pack.",
            "https://www.lumo22.com/account",
            new_price_display="£96",
            old_price_display="£79",
        ),
    ))

    # 9. Subscription cancelled
    samples.append((
        "subscription_cancelled.html",
        "Subscription cancelled confirmation",
        _subscription_cancelled_email_html("https://www.lumo22.com/captions"),
    ))

    # 10. Plan change confirmation (downgrade/reduce)
    samples.append((
        "plan_change_reduce.html",
        "Plan change confirmation (downgrade/reduce platforms/remove Stories)",
        _plan_change_confirmation_email_html(
            "What changed: your subscription now includes 1 platform instead of 3; Story Ideas has been removed from your subscription.",
            "Changes apply to your next pack. Packs already delivered will not change.",
            "https://www.lumo22.com/account",
            new_price_display="£79",
            old_price_display="£115",
        ),
    ))

    import re
    for filename, label, html in samples:
        path = out_dir / filename
        # Use relative path for logo so it loads when viewing locally (file://)
        html = re.sub(r'src="[^"]*static/images/logo\.png"', 'src="../static/images/logo.png"', html)
        path.write_text(html, encoding="utf-8")
        index_lines.append(f'  <li><a href="{filename}" target="_blank">{label}</a></li>')
        print(f"  Written: {path}")

    # Index page
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Lumo 22 email samples</title></head>
<body style="font-family: system-ui; padding: 2rem; max-width: 600px;">
  <h1>Lumo 22 — email samples</h1>
  <p>Preview how your branded emails look. Open each link in a new tab:</p>
  <ul>
{"\n".join(index_lines)}
  </ul>
  <p style="margin-top: 2rem; color: #666;">Run <code>python3 scripts/generate_email_samples.py</code> to regenerate.</p>
</body>
</html>
"""
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  Written: {out_dir / 'index.html'}")

    print(f"\nDone. Open {out_dir / 'index.html'} in your browser to view all samples.")
    print(f"  Path: {out_dir.absolute()}")

if __name__ == "__main__":
    main()
