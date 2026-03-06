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
        _login_link_email_html,
        _email_change_verification_html,
    )

    out_dir = project_root / "email_samples"
    out_dir.mkdir(exist_ok=True)
    index_lines = []

    samples = []

    # 1. Intake email (after captions purchase)
    intake_body = """Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

https://www.lumo22.com/captions-intake?t=sample-token

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""
    samples.append(("intake.html", "Intake link (after captions purchase)", _branded_html_email(intake_body)))

    # 2. Delivery email (plain — actual has PDF attached)
    delivery_body = """Hi,

Your 30 Days of Social Media Captions are ready.

Attached you'll find your 30_Days_Captions.pdf (and 30_Days_Stories.pdf if you added Story Ideas).

Copy, edit, and post. If you need anything, just reply.

Lumo 22
"""
    samples.append(("delivery.html", "Delivery email (with attachment)", _branded_html_email(delivery_body)))

    # 3. Password reset
    samples.append(("password_reset.html", "Password reset", _password_reset_email_html("https://www.lumo22.com/reset-password?token=sample-token")))

    # 4. Login link
    samples.append(("login_link.html", "Login link (magic link)", _login_link_email_html("https://www.lumo22.com/login?login_token=sample-token")))

    # 5. Email change verification
    samples.append(("email_change.html", "Email change verification", _email_change_verification_html("https://www.lumo22.com/change-email-confirm?token=sample-token")))

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
