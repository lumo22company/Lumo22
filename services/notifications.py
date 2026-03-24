"""
Notification service for emails and SMS.
Handles automated follow-ups and booking confirmations.
Uses Lumo 22 brand (BRAND_STYLE_GUIDE): black, gold accent, Century Gothic.
"""
import os
import re
from typing import Dict, Any, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Attachment, FileContent, FileName, FileType
import base64
from twilio.rest import Client as TwilioClient
from config import Config

# Brand (from BRAND_STYLE_GUIDE.md) — matches caption_pdf.py aesthetic
BRAND_BLACK = "#000000"
BRAND_GOLD = "#fff200"
BRAND_TEXT = "#000000"
BRAND_MUTED = "#9a9a96"
BRAND_TEXT_ON_DARK = "#F5F5F2"
BRAND_FONT = "Century Gothic, CenturyGothic, Apple Gothic, sans-serif"


def _get_logo_url() -> str:
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://lumo22.com"
    return f"{base}/static/images/logo.png"


def _email_header_html() -> str:
    """PDF-style dark header band — black bg, gold wordmark."""
    return f"""<tr>
      <td style="padding: 24px 32px; background: {BRAND_BLACK}; text-align: left;">
        <p style="margin:0; font-size: 13px; letter-spacing: 0.2em; text-transform: uppercase; color: {BRAND_GOLD}; font-weight: 600; font-family: {BRAND_FONT};">Lumo 22</p>
      </td>
    </tr>"""


def _email_footer_html() -> str:
    """PDF-style dark footer — cohesive with header."""
    logo_url = _get_logo_url()
    return f"""<tr>
      <td style="padding: 24px 32px; background: {BRAND_BLACK}; font-size: 12px; color: {BRAND_MUTED}; font-family: {BRAND_FONT};">
        <p style="margin:0 0 12px;"><img src="{logo_url}" alt="Lumo 22" width="100" height="auto" style="display:block; height:auto; max-width:100px; opacity: 0.9;" /></p>
        <p style="margin:0;"><a href="mailto:hello@lumo22.com" style="color:{BRAND_GOLD}; text-decoration:none;">hello@lumo22.com</a></p>
        <p style="margin:10px 0 0; color: rgba(245,245,242,0.7); font-size: 11px;">Lighting the way to smarter socials</p>
      </td>
    </tr>"""


def _email_wrapper(content: str) -> str:
    """Wrap content in PDF-cohesive email shell (header + content + footer)."""
    header = _email_header_html()
    footer = _email_footer_html()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lumo 22</title>
</head>
<body style="margin:0; padding:0; background:#e5e5e5; font-family: {BRAND_FONT}; font-size: 16px; line-height: 1.7; color: {BRAND_TEXT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#e5e5e5;">
    <tr>
      <td style="padding: 32px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 0; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
          {header}
          <tr>
            <td style="padding: 40px 32px 36px; color: {BRAND_TEXT};">
              {content}
            </td>
          </tr>
          {footer}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _captions_delivery_email_html(
    has_stories: bool,
    has_subscription: bool = False,
    backup_captions_url: str = "",
    backup_stories_url: str = "",
) -> str:
    """Build explicit HTML for the 30 Days captions delivery email so the body always shows."""
    if has_stories:
        content = """<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. Both documents are attached.</p>
<p style="margin:0 0 16px;">Copy each caption and story idea as you need them, or edit to fit.</p>"""
    else:
        content = """<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions are ready. The document is attached.</p>
<p style="margin:0 0 16px;">Copy each caption as you need it, or edit to fit.</p>"""
    if has_subscription:
        content += """
<p style="margin:0 0 16px; font-size:14px; color:#666;">Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account → Manage subscription.</p>"""
    if backup_captions_url:
        safe_captions = backup_captions_url.replace('"', "%22")
        content += f"""
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">If attachments don't appear in your inbox, use your backup download link(s):</p>
<p style="margin:0 0 8px;"><a href="{safe_captions}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">Download captions PDF</a></p>"""
        if backup_stories_url:
            safe_stories = backup_stories_url.replace('"', "%22")
            content += f"""
<p style="margin:0 0 16px;"><a href="{safe_stories}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">Download stories PDF</a></p>"""
    content += "\n<p style=\"margin:0;\">— Lumo 22</p>"
    return _email_wrapper(content)


def _captions_reminder_email_html(login_url: str, account_url: str) -> str:
    """Build explicit HTML for the captions intake reminder email. Subscribers must log in first; link goes to login then redirects to form."""
    import html
    login_url = (login_url or "").strip()
    account_url = (account_url or "").strip()
    if not login_url or not login_url.startswith("http"):
        login_url = ""
    if not account_url or not account_url.startswith("http"):
        account_url = ""
    safe_login = html.escape(login_url, quote=True)
    safe_account = html.escape(account_url, quote=True)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Your next 30 Days of Social Media Captions pack is coming soon. You can update your preferences (business details, voice, platforms) anytime before we generate it.</p>
<p style="margin:0 0 16px;">Do you have an event, promotion or something else coming up? Use your form to tell us about it and we'll tailor your captions to fit.</p>
<p style="margin:0 0 12px; font-size:14px; color:{BRAND_MUTED};"><strong style="color:{BRAND_TEXT};">You'll need to log in to your account first</strong>, then you'll be taken to your form.</p>
<p style="margin:0 0 24px;"><a href="{safe_login}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Log in to update your form</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_login}</p>
<p style="margin:0 0 16px;">This takes about 2 minutes. If you don't change anything, we'll use your existing details.</p>
<p style="margin:0 0 16px;">You can turn these reminders off in your <a href="{safe_account}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">account</a>.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _branded_html_email(body_plain: str) -> str:
    """Wrap plain body in Lumo 22 branded HTML (PDF aesthetic: black header/footer, gold accent)."""
    import html
    body_plain = (body_plain or "").strip()
    lines = body_plain.split("\n")
    escaped_lines = []
    for line in lines:
        line = html.escape(line)
        line = re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" style="color:' + BRAND_GOLD + "; text-decoration: none; border-bottom: 1px solid " + BRAND_GOLD + ';">\1</a>',
            line,
        )
        escaped_lines.append(line)
    body_html = "<br>\n".join(escaped_lines)
    content = f'<div style="font-family: ' + BRAND_FONT + ';">{body_html}</div>'
    return _email_wrapper(content)


def _password_reset_email_html(reset_url: str) -> str:
    """Build branded HTML for password reset — PDF aesthetic (dark header/footer, black CTA)."""
    import html
    if not reset_url or not reset_url.startswith("http"):
        reset_url = ""
    safe_url = html.escape(reset_url, quote=True)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">You requested a password reset for your Lumo 22 account.</p>
<p style="margin:0 0 12px;">Click the link below to set a new password (link expires in 1 hour):</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Reset my password</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">If you didn't request this, you can ignore this email. Your password will stay the same.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _build_intake_order_summary(order: Optional[Dict[str, Any]]) -> Optional[str]:
    """Build a short order summary for the intake email. Returns None if no order or nothing to show."""
    if not order or not isinstance(order, dict):
        return None
    n = max(1, min(4, int(order.get("platforms_count") or 1)))
    is_sub = bool((order.get("stripe_subscription_id") or "").strip())
    platforms_label = "1 platform" if n == 1 else f"{n} platforms"
    order_type = "Subscription (£79/month)" if is_sub else "One-off (£97)"
    selected = (order.get("selected_platforms") or "").strip()
    if selected:
        platforms_detail = selected
    else:
        platforms_detail = platforms_label
    stories = bool(order.get("include_stories"))
    lines = [
        f"• {order_type}",
        f"• {platforms_detail}",
    ]
    if stories:
        lines.append("• 30 Days Story Ideas included")
    return "\n".join(lines)


def _format_amount_paid(amount_total: Optional[int], currency: str) -> Optional[str]:
    """Format Stripe amount_total (pence/cents) for display. Returns None if invalid."""
    if amount_total is None or not isinstance(amount_total, (int, float)):
        return None
    try:
        amt = int(amount_total)
    except (TypeError, ValueError):
        return None
    currency = (currency or "gbp").strip().lower()
    if currency == "gbp":
        return f"£{amt / 100:.2f}"
    if currency == "usd":
        return f"${amt / 100:.2f}"
    if currency == "eur":
        return f"€{amt / 100:.2f}"
    return f"{amt / 100:.2f} {currency.upper()}"


def _order_receipt_email_html(order_summary: Optional[str] = None, amount_paid: Optional[str] = None) -> str:
    """Build branded HTML for order receipt — payment received, products, price, intake link coming soon."""
    import html
    receipt_block = ""
    if order_summary or amount_paid:
        lines = []
        if order_summary and order_summary.strip():
            summary_escaped = html.escape(order_summary.strip()).replace("\n", "<br>\n")
            lines.append(summary_escaped)
        if amount_paid:
            lines.append(f"<strong>Amount paid:</strong> {html.escape(amount_paid)}")
        if lines:
            receipt_block = f"""<p style="margin:0 0 16px; font-size:14px; color:{BRAND_MUTED}; border:1px solid rgba(0,0,0,0.08); border-radius:8px; padding:16px; background:#fafafa;"><strong style="color:{BRAND_TEXT};">Order details</strong><br>{'<br>'.join(lines)}</p>
"""
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Thanks for your order. We've received your payment for 30 Days of Social Media Captions.</p>
{receipt_block}<p style="margin:0 0 16px;">You'll receive an email soon with a link to complete your short intake form (about 2 minutes). Once you submit, we'll generate your captions and send them to you by email within a few minutes.</p>
<p style="margin:0 0 16px;">If you don't see the intake email, check your spam folder.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _get_login_url() -> str:
    """Base URL for customer login (used in emails)."""
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://www.lumo22.com"
    return f"{base}/login"


def _get_signup_url() -> str:
    """Base URL for customer signup (used in emails)."""
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://www.lumo22.com"
    return f"{base}/signup"


def _subscription_welcome_prefilled_email_html(login_url: str, intake_url: str) -> str:
    """Branded HTML for subscription welcome when upgraded from one-off. They already have an account; log in to access prefilled form."""
    import html
    login_url = (login_url or "").strip() or _get_login_url()
    intake_url = (intake_url or "").strip()
    safe_login = html.escape(login_url, quote=True)
    safe_intake = html.escape(intake_url, quote=True) if intake_url and intake_url.startswith("http") else ""
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">You're subscribed to 30 Days of Social Media Captions. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.</p>
<p style="margin:0 0 24px;"><a href="{safe_login}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Log in to your account</a></p>
<p style="margin:0 0 12px;">Open your form (prefilled); you can edit it anytime in your account:</p>
<p style="margin:0 0 24px;"><a href="{safe_intake}" style="display:inline-block; padding:12px 24px; background:#f0f0f0; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Open your form</a></p>
<p style="margin:0 0 16px;">If you have any questions, just reply to this email.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _subscription_upgrade_confirmation_email_html(
    login_url: str, intake_url: str, first_charge_date: Optional[str] = None
) -> str:
    """Branded HTML for upgrade confirmation when trial (no charge today). Charge when first pack is ready."""
    import html
    login_url = (login_url or "").strip() or _get_login_url()
    intake_url = (intake_url or "").strip()
    safe_login = html.escape(login_url, quote=True)
    safe_intake = html.escape(intake_url, quote=True) if intake_url and intake_url.startswith("http") else ""
    sooner_p = (
        f'<p style="margin:0 0 16px;">If you want your subscription pack sooner, you can do this in '
        f'<a href="{safe_login}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">your account</a>.</p>'
    )
    charge_p = ""
    if first_charge_date:
        charge_p = (
            f'<p style="margin:0 0 16px;">You won\'t be charged today. We\'ll charge your card when your first '
            f"subscription pack is ready on {html.escape(first_charge_date)} (30 days after your one-off pack).</p>"
            + sooner_p
        )
    else:
        charge_p = (
            '<p style="margin:0 0 16px;">You won\'t be charged today. We\'ll charge your card when your first '
            "subscription pack is ready (about 30 days after your one-off pack).</p>"
            + sooner_p
        )
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">You're set up for your 30 Days Captions subscription. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.</p>
{charge_p}
<p style="margin:0 0 24px;"><a href="{safe_login}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Log in to your account</a></p>
<p style="margin:0 0 12px;">Open your form (prefilled); you can edit it anytime in your account:</p>
<p style="margin:0 0 24px;"><a href="{safe_intake}" style="display:inline-block; padding:12px 24px; background:#f0f0f0; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Open your form</a></p>
<p style="margin:0 0 16px;">If you have any questions, just reply to this email.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _intake_link_email_html(intake_url: str, order_summary: Optional[str] = None, is_subscription: bool = False) -> str:
    """Build branded HTML for captions intake link email — PDF aesthetic, explicit body so it always shows."""
    import html
    intake_url = (intake_url or "").strip()
    if not intake_url or not intake_url.startswith("http"):
        intake_url = ""
    safe_url = html.escape(intake_url, quote=True)
    login_url = _get_login_url()
    safe_login = html.escape(login_url, quote=True)
    summary_block = ""
    if order_summary and order_summary.strip():
        summary_escaped = html.escape(order_summary.strip()).replace("\n", "<br>\n")
        summary_block = f"""<p style="margin:0 0 16px; font-size:14px; color:{BRAND_MUTED};"><strong style="color:{BRAND_TEXT};">Order confirmation</strong><br>Here's what you ordered:<br>{summary_escaped}</p>
"""
    account_line = "On the form you can also create an account to access your captions and manage your subscription in one place." if is_subscription else "On the form you can also create an account to access your captions in one place."
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.</p>
{summary_block}<p style="margin:0 0 12px;">Please complete this short form so we can create your captions. It takes about 2 minutes.</p>
<p style="margin:0 0 12px; font-size:14px; color:{BRAND_MUTED};"><strong style="color:{BRAND_TEXT};">For security:</strong> If you already have a Lumo 22 account, <a href="{safe_login}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">log in first</a>, then use the button below to open your form.</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Complete the form</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.</p>
<p style="margin:0 0 16px;">{html.escape(account_line)}</p>
<p style="margin:0 0 16px;">Thanks for choosing us.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _captions_intake_reminder_email_html(intake_url: str) -> str:
    """Branded HTML for one-off intake reminder (customer hasn't completed form yet)."""
    import html
    intake_url = (intake_url or "").strip()
    if not intake_url or not intake_url.startswith("http"):
        intake_url = ""
    safe_url = html.escape(intake_url, quote=True)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Thanks for your order of 30 Days of Social Media Captions.</p>
<p style="margin:0 0 16px;">Before we can start writing, we need a few details about your business, audience, and voice.</p>
<p style="margin:0 0 12px;">Complete this short form so we can create your pack:</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Complete your form</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">This takes about 5–10 minutes. Once it's done, we'll generate your captions and email your pack.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _one_off_upgrade_reminder_email_html(upgrade_url: str, unsubscribe_url: str, business_name: Optional[str] = None) -> str:
    """Branded HTML for one-off → subscription upgrade reminder (a few days before day 30)."""
    import html
    upgrade_url = (upgrade_url or "").strip()
    unsubscribe_url = (unsubscribe_url or "").strip()
    safe_upgrade = html.escape(upgrade_url, quote=True) if upgrade_url and upgrade_url.startswith("http") else ""
    safe_unsub = html.escape(unsubscribe_url, quote=True) if unsubscribe_url and unsubscribe_url.startswith("http") else ""
    intro = "Your 30 days of captions are almost up."
    if business_name:
        intro = f"Your 30 days of captions for {html.escape(business_name)} are almost up."
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">{intro} Want a new pack every month? Upgrade to a subscription and your next pack will be delivered 30 days after your current one—continuous content, no overlap.</p>
<p style="margin:0 0 12px;">You'll need to log in or create an account first; then you can complete the upgrade. Your form answers will be prefilled so checkout is quick—you can edit your form anytime in your account after you subscribe.</p>
<p style="margin:0 0 24px;"><a href="{safe_upgrade}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Upgrade to subscription</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{html.escape(upgrade_url or '')}</p>
<p style="margin:0 0 24px; font-size:13px; color:{BRAND_MUTED};"><a href="{safe_unsub}" style="color:{BRAND_MUTED}; text-decoration:underline;">Unsubscribe from upgrade reminders</a></p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _welcome_and_verify_email_html(verify_url: str) -> str:
    """Build branded HTML for welcome + email verification — single email after signup."""
    import html
    if not verify_url or not str(verify_url).strip().startswith("http"):
        verify_url = ""
    safe_url = html.escape(verify_url, quote=True)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Welcome to Lumo 22. You've created an account.</p>
<p style="margin:0 0 16px;">To get started, please verify your email address by clicking the link below (link expires in 24 hours):</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Verify my email</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">Once verified, you can log in to your account, buy 30 Days of Social Media Captions, or manage your subscription.</p>
<p style="margin:0 0 16px;">If you didn't create this account, you can ignore this email.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _subscription_cancelled_email_html(
    captions_url: str,
    plan_summary: str | None = None,
    price_display: str | None = None,
) -> str:
    """Build branded HTML for subscription cancelled confirmation."""
    import html
    safe_url = html.escape(captions_url or "", quote=True)
    summary_line = ""
    if plan_summary or price_display:
        parts = []
        if plan_summary:
            parts.append(html.escape(plan_summary, quote=False))
        if price_display:
            parts.append(html.escape(price_display, quote=False))
        summary_line = f'<p style="margin:0 0 16px;"><strong>What you cancelled:</strong> {" — ".join(parts)}</p>'
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions subscription has been cancelled. Your subscription stays active until the end of your current billing period. After that, you can still access your past captions in your account at any time.</p>
{summary_line}
<p style="margin:0 0 16px;">We're sorry to see you go. If you change your mind, you can subscribe again anytime at <a href="{safe_url}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">lumo22.com/captions</a>.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _plan_change_confirmation_email_html(
    change_summary: str,
    when_effective: str,
    account_url: str,
    new_price_display: str | None = None,
    old_price_display: str | None = None,
) -> str:
    """Build branded HTML for plan change (upgrade/downgrade/add-on) confirmation."""
    import html
    raw_summary = change_summary or "Your plan has been updated."
    safe_summary = html.escape(raw_summary, quote=False)
    if safe_summary.startswith("What changed: "):
        summary_html = f'<strong>What changed:</strong> {safe_summary[14:]}'
    else:
        summary_html = safe_summary
    safe_when = html.escape(when_effective or "Changes apply to your next pack.", quote=False)
    safe_account = html.escape(account_url or "", quote=True)
    price_line = ""
    if new_price_display:
        if old_price_display:
            price_line = f'<p style="margin:0 0 16px;"><strong>New price:</strong> {html.escape(new_price_display)}/month (was {html.escape(old_price_display)}/month).</p>'
        else:
            price_line = f'<p style="margin:0 0 16px;"><strong>New price:</strong> {html.escape(new_price_display)}/month.</p>'
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 12px;">You made changes to your Lumo 22 subscription.</p>
<p style="margin:0 0 16px;">{summary_html}</p>
{price_line}
<p style="margin:0 0 16px;"><strong>When does this take effect?</strong> {safe_when}</p>
<p style="margin:0 0 16px;">You can manage your subscription anytime in your <a href="{safe_account}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">account</a>.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _email_change_verification_html(confirm_url: str) -> str:
    """Build branded HTML for email change verification — PDF aesthetic (dark header/footer, black CTA)."""
    import html
    if not confirm_url or not confirm_url.startswith("http"):
        confirm_url = ""
    safe_url = html.escape(confirm_url, quote=True)
    content = f"""<p style="margin:0 0 16px;">You requested to change the email address for your Lumo 22 account to this address.</p>
<p style="margin:0 0 12px;">Click the link below to confirm the change (link expires in 1 hour):</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Confirm email change</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">If you didn't request this, you can ignore this email. Your email address will stay the same.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _sanitize_email_value(s: str) -> str:
    """Remove control chars so SendGrid doesn't raise 'Invalid non-printable ASCII'."""
    if not s or not isinstance(s, str):
        return (s or "").strip()
    return re.sub(r"[\x00-\x1f\x7f]", "", s.strip())

class NotificationService:
    """Service for sending emails and SMS notifications"""
    
    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        
        api_key = (Config.SENDGRID_API_KEY or "").strip()
        api_key = re.sub(r"[\x00-\x1f\x7f]", "", api_key)
        if api_key:
            self.sendgrid_client = SendGridAPIClient(api_key=api_key)
        
        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
            self.twilio_client = TwilioClient(
                Config.TWILIO_ACCOUNT_SID,
                Config.TWILIO_AUTH_TOKEN
            )
    
    def send_lead_notification(
        self,
        lead_email: str,
        lead_name: str,
        service_type: str,
        booking_link: Optional[str] = None
    ) -> bool:
        """
        Send notification to lead with booking information.
        
        Returns:
            bool indicating success
        """
        subject = f"Thank you for your interest in {service_type}"
        
        if booking_link:
            body = f"""
Hi {lead_name},

Thank you for your interest in our {service_type} services!

We'd love to schedule a time to discuss your needs. Please book a convenient time using the link below:

{booking_link}

If you have any questions, feel free to reply to this email.

Best regards,
{Config.BUSINESS_NAME}
"""
        else:
            body = f"""
Hi {lead_name},

Thank you for your interest in our {service_type} services!

We'll be in touch shortly to discuss your needs.

Best regards,
{Config.BUSINESS_NAME}
"""
        
        return self.send_email(lead_email, subject, body)
    
    def send_internal_notification(
        self,
        admin_email: str,
        lead_name: str,
        lead_email: str,
        service_type: str,
        qualification_score: int,
        booking_link: Optional[str] = None
    ) -> bool:
        """
        Send internal notification to business owner about new lead.
        
        Returns:
            bool indicating success
        """
        subject = f"New Lead: {lead_name} - {service_type} (Score: {qualification_score})"
        
        body = f"""
New Lead Received:

Name: {lead_name}
Email: {lead_email}
Service: {service_type}
Qualification Score: {qualification_score}/100

{f'Booking Link: {booking_link}' if booking_link else 'No booking link generated'}

---
This is an automated notification from your lead capture system.
"""
        
        return self.send_email(admin_email, subject, body)

    def send_password_reset_email(self, to_email: str, reset_url: str) -> bool:
        """Send password reset email with plain and HTML body; link is explicit in HTML so it always appears."""
        if not reset_url or not reset_url.startswith("http"):
            print(f"[SendGrid] Password reset NOT sent: invalid reset_url (empty or not http)")
            return False
        subject = "Reset your Lumo 22 password"
        body = f"""Hi,

You requested a password reset for your Lumo 22 account.

Click the link below to set a new password (link expires in 1 hour):

{reset_url}

If the link doesn't work, copy and paste the link above into your browser.

If you didn't request this, you can ignore this email. Your password will stay the same.

— Lumo 22
"""
        html_body = _password_reset_email_html(reset_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_welcome_and_verification_email(self, to_email: str, verify_url: str) -> bool:
        """Send welcome + email verification (combined). One email after signup."""
        if not verify_url or not str(verify_url).strip().startswith("http"):
            print("[SendGrid] Welcome/verification email NOT sent: invalid verify_url")
            return False
        subject = "Welcome to Lumo 22 — verify your email"
        body = """Hi,

Welcome to Lumo 22. You've created an account.

To get started, please verify your email address by clicking the link below (link expires in 24 hours):

""" + verify_url + """

Once verified, you can log in to your account, buy 30 Days of Social Media Captions, or manage your subscription.

If you didn't create this account, you can ignore this email.

— Lumo 22"""
        html_body = _welcome_and_verify_email_html(verify_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_plan_change_confirmation_email(
        self,
        to_email: str,
        change_summary: str,
        when_effective: str,
        account_url: str,
        new_price_display: str | None = None,
        old_price_display: str | None = None,
    ) -> bool:
        """Send confirmation when customer upgrades, downgrades, or adds Stories."""
        subject = "Your Lumo 22 plan has been updated"
        price_block = ""
        if new_price_display:
            if old_price_display:
                price_block = f"\nNew price: {new_price_display}/month (was {old_price_display}/month).\n"
            else:
                price_block = f"\nNew price: {new_price_display}/month.\n"
        body = f"""Hi,

You made changes to your Lumo 22 subscription.

{change_summary or "Your plan has been updated."}
{price_block}
When does this take effect? {when_effective or "Changes apply to your next pack."}

You can manage your subscription anytime in your account: {account_url or ""}

— Lumo 22"""
        html_body = _plan_change_confirmation_email_html(
            change_summary, when_effective, account_url,
            new_price_display=new_price_display,
            old_price_display=old_price_display,
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_cancelled_email(
        self,
        to_email: str,
        captions_url: str,
        plan_summary: str | None = None,
        price_display: str | None = None,
    ) -> bool:
        """Send confirmation when customer cancels their subscription."""
        subject = "Your subscription has been cancelled"
        summary_block = ""
        if plan_summary or price_display:
            parts = []
            if plan_summary:
                parts.append(plan_summary)
            if price_display:
                parts.append(price_display)
            summary_block = f"\n\nWhat you cancelled: {' — '.join(parts)}\n"
        body = f"""Hi,

Your 30 Days of Social Media Captions subscription has been cancelled. Your subscription stays active until the end of your current billing period. After that, you can still access your past captions in your account at any time.{summary_block}
We're sorry to see you go. If you change your mind, you can subscribe again anytime at {captions_url or "lumo22.com/captions"}.

— Lumo 22"""
        html_body = _subscription_cancelled_email_html(
            captions_url, plan_summary=plan_summary, price_display=price_display
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_email_change_verification_email(self, to_email: str, confirm_url: str) -> bool:
        """Send email change verification to the NEW email address; link confirms the change."""
        if not confirm_url or not confirm_url.startswith("http"):
            print("[SendGrid] Email change verification NOT sent: invalid confirm_url")
            return False
        subject = "Confirm your new email address"
        body = f"""Hi,

You requested to change the email address for your Lumo 22 account to this address.

Click the link below to confirm the change (link expires in 1 hour):

{confirm_url}

If you didn't request this, you can ignore this email. Your email address will stay the same.

— Lumo 22
"""
        html_body = _email_change_verification_html(confirm_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_order_receipt_email(
        self,
        to_email: str,
        order: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
    ) -> bool:
        """Send order receipt (payment received, products, price, intake link coming soon). Sent right after checkout.
        order: caption order dict for product summary. session: Stripe checkout session for amount_paid."""
        subject = "Thanks for your order — 30 Days of Social Media Captions"
        order_summary = _build_intake_order_summary(order) if order else None
        amount_paid = None
        currency = "gbp"
        if session:
            amt_raw = session.get("amount_total") if hasattr(session, "get") else getattr(session, "amount_total", None)
            curr_raw = session.get("currency") if hasattr(session, "get") else getattr(session, "currency", "gbp")
            currency = str(curr_raw or "gbp").strip().lower() if curr_raw else "gbp"
            amount_paid = _format_amount_paid(amt_raw, currency)

        body_lines = [
            "Hi,",
            "",
            "Thanks for your order. We've received your payment for 30 Days of Social Media Captions.",
            "",
        ]
        if order_summary or amount_paid:
            body_lines.append("Order details:")
            if order_summary:
                body_lines.append(order_summary)
            if amount_paid:
                body_lines.append(f"Amount paid: {amount_paid}")
            body_lines.extend(["", ""])
        body_lines.extend([
            "You'll receive an email soon with a link to complete your short intake form (about 2 minutes). "
            "Once you submit, we'll generate your captions and send them to you by email within a few minutes.",
            "",
            "If you don't see the intake email, check your spam folder.",
            "",
            "— Lumo 22",
        ])
        body = "\n".join(body_lines)
        html_body = _order_receipt_email_html(order_summary=order_summary, amount_paid=amount_paid)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_intake_link_email(self, to_email: str, intake_url: str, order: Optional[Dict[str, Any]] = None) -> bool:
        """Send captions intake form link email with explicit HTML body. Optionally include order summary."""
        if not intake_url or not str(intake_url).strip().startswith("http"):
            print("[SendGrid] Intake link email NOT sent: invalid intake_url")
            return False
        subject = "Your 30 Days of Social Media Captions - next step"
        order_summary = _build_intake_order_summary(order) if order else None
        body = "Hi,\n\nThanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.\n\n"
        if order_summary:
            body += "Order confirmation — here's what you ordered:\n" + order_summary + "\n\n"
        body += "Please complete this short form so we can create your captions. It takes about 2 minutes.\n\n"
        base = (Config.BASE_URL or "").strip().rstrip("/")
        login_url = f"{base}/login" if base and base.startswith("http") else "https://www.lumo22.com/login"
        body += "For security: If you already have a Lumo 22 account, log in first (" + login_url + "), then use the link below to open your form.\n\n"
        body += intake_url
        is_sub = bool(order and (order.get("stripe_subscription_id") or "").strip())
        account_line = "On the form you can also create an account to access your captions and manage your subscription in one place." if is_sub else "On the form you can also create an account to access your captions in one place."
        body += "\n\nOnce you submit, we'll generate your 30 captions and send them to you by email within a few minutes.\n\n" + account_line + "\n\nThanks for choosing us.\n\nLumo 22"
        html_body = _intake_link_email_html(intake_url, order_summary, is_subscription=is_sub)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_welcome_prefilled_email(
        self, to_email: str, intake_url: str
    ) -> bool:
        """Send welcome email when customer upgraded from one-off to subscription (and was charged at checkout, e.g. get pack now). Form is prefilled."""
        if not to_email or "@" not in str(to_email):
            return False
        subject = "You're subscribed — 30 Days Captions"
        login_url = _get_login_url()
        body = """Hi,

You're subscribed to 30 Days of Social Media Captions. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.

Log in to your account: """ + login_url + """

Open your form (prefilled); you can edit it anytime in your account: """ + (intake_url or "") + """

If you have any questions, just reply to this email.

— Lumo 22
"""
        html_body = _subscription_welcome_prefilled_email_html(login_url, intake_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_upgrade_confirmation_email(
        self, to_email: str, intake_url: str, first_charge_date: Optional[str] = None
    ) -> bool:
        """Confirmation when customer upgraded from one-off to subscription with trial (no charge today). You'll be charged when first pack is ready."""
        if not to_email or "@" not in str(to_email):
            return False
        subject = "You're set up — 30 Days Captions subscription"
        login_url = _get_login_url()
        sooner_line = (
            "\nIf you want your subscription pack sooner, you can do this in your account.\n"
        )
        charge_line = ""
        if first_charge_date:
            charge_line = (
                "\nYou won't be charged today. We'll charge your card when your first subscription pack is ready on "
                + first_charge_date
                + " (30 days after your one-off pack)."
                + sooner_line
            )
        else:
            charge_line = (
                "\nYou won't be charged today. We'll charge your card when your first subscription pack is ready "
                "(about 30 days after your one-off pack)."
                + sooner_line
            )
        body = """Hi,

You're set up for your 30 Days Captions subscription. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.
""" + charge_line + """
Log in to your account: """ + login_url + """

Open your form (prefilled); you can edit it anytime in your account: """ + (intake_url or "") + """

If you have any questions, just reply to this email.

— Lumo 22
"""
        html_body = _subscription_upgrade_confirmation_email_html(login_url, intake_url, first_charge_date)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_one_off_upgrade_reminder_email(
        self,
        to_email: str,
        upgrade_url: str,
        unsubscribe_url: str,
        business_name: Optional[str] = None,
    ) -> bool:
        """Send one-off → subscription upgrade reminder (a few days before day 30). Includes opt-out link."""
        if not upgrade_url or not str(upgrade_url).strip().startswith("http"):
            return False
        subject = "Your 30 days of captions — upgrade to a subscription?"
        intro = "Your 30 days of captions are almost up."
        if business_name:
            intro = f"Your 30 days of captions for {business_name} are almost up."
        body = f"""Hi,

{intro} Want a new pack every month? Upgrade to a subscription and your next pack will be delivered 30 days after your current one—continuous content, no overlap.

You'll need to log in or create an account first; then you can complete the upgrade. Your form answers will be prefilled so checkout is quick—you can edit your form anytime in your account after you subscribe.

{upgrade_url}

Unsubscribe from upgrade reminders: {unsubscribe_url}

— Lumo 22
"""
        html_body = _one_off_upgrade_reminder_email_html(upgrade_url, unsubscribe_url, business_name)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using SendGrid.
        
        Returns:
            bool indicating success
        """
        to_email = _sanitize_email_value(to_email or "")
        if not to_email or "@" not in to_email:
            print(f"[SendGrid] Email NOT sent (invalid to_email): subject={subject!r}")
            return False
        body = (body or "").strip()
        if not body:
            print(f"[SendGrid] Email NOT sent (empty body): subject={subject!r} to={to_email}")
            return False
        if not self.sendgrid_client:
            print(f"[SendGrid] Email NOT sent (no API key): subject={subject!r} to={to_email}")
            return False

        try:
            from_addr = _sanitize_email_value(Config.FROM_EMAIL or "") or "noreply@lumo22.com"
            from_name = (Config.FROM_NAME or "Lumo 22").strip() or "Lumo 22"
            html_content = html_body if html_body is not None else _branded_html_email(body)
            message = Mail(
                from_email=Email(from_addr, from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html_content
            )
            response = self.sendgrid_client.send(message)
            status = getattr(response, "status_code", None)
            ok = status in [200, 201, 202]
            if ok:
                print(f"[SendGrid] Email sent OK (status={status}) from={from_addr!r} to={to_email} subject={subject!r}")
            else:
                body_preview = getattr(response, "body", "") or ""
                if isinstance(body_preview, bytes):
                    body_preview = body_preview.decode("utf-8", errors="replace")[:500]
                else:
                    body_preview = str(body_preview)[:500]
                print(f"[SendGrid] Email rejected (status={status}) from={from_addr!r} to={to_email} subject={subject!r} body={body_preview!r}")
            return ok
        except Exception as e:
            import traceback
            print(f"[SendGrid] Error sending email to {to_email}: {e}")
            traceback.print_exc()
            return False

    def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        filename: str,
        file_content: Optional[str] = None,
        file_content_bytes: Optional[bytes] = None,
        mime_type: str = "text/plain",
        extra_attachments: Optional[list] = None,
        html_content: Optional[str] = None,
    ) -> tuple:
        """Send email with one or more attachments. Returns (True, None) on success, (False, error_message) on failure.
        Attachments appear in the email in this order: primary (filename/file_content*) first, then each
        extra_attachments entry in list order (SendGrid prepends internally; we reverse so this order is preserved).
        extra_attachments: optional list of {"filename": str, "content": bytes, "mime_type": str} for additional files.
        html_content: optional explicit HTML body; if not set, body is converted via _branded_html_email."""
        to_email = _sanitize_email_value(to_email or "")
        if not to_email or "@" not in to_email:
            msg = "Invalid or missing recipient email"
            print(f"[SendGrid] Email with attachment NOT sent (invalid to_email): subject={subject!r}")
            return (False, msg)
        body = (body or "").strip()
        if not body:
            msg = "Email body is empty"
            print(f"[SendGrid] Email with attachment NOT sent (empty body): subject={subject!r} to={to_email}")
            return (False, msg)
        if not self.sendgrid_client:
            msg = "SendGrid not configured (missing SENDGRID_API_KEY)"
            print(f"[SendGrid] Email with attachment NOT sent (no API key): subject={subject!r} to={to_email}")
            return (False, msg)

        def b64_for(data: bytes) -> str:
            return base64.b64encode(data).decode("ascii")

        attachments_to_add = []
        if file_content_bytes is not None:
            attachments_to_add.append((filename, b64_for(file_content_bytes), mime_type))
        elif file_content is not None:
            attachments_to_add.append((filename, b64_for(file_content.encode("utf-8")), mime_type))

        for extra in (extra_attachments or []):
            fn = extra.get("filename")
            content = extra.get("content")
            mt = extra.get("mime_type", "application/octet-stream")
            if fn and content is not None:
                attachments_to_add.append((fn, b64_for(content), mt))

        if not attachments_to_add:
            msg = "No attachment content (need file_content/file_content_bytes or extra_attachments)"
            print("[SendGrid] send_email_with_attachment: " + msg)
            return (False, msg)
        try:
            from_addr = _sanitize_email_value(Config.FROM_EMAIL or "") or "noreply@lumo22.com"
            from_name = (Config.FROM_NAME or "Lumo 22").strip() or "Lumo 22"
            html_body = html_content if html_content is not None else _branded_html_email(body)
            message = Mail(
                from_email=Email(from_addr, from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html_body,
            )
            attachment_list = []
            for fn, enc, mt in attachments_to_add:
                att = Attachment(
                    file_content=FileContent(enc),
                    file_name=FileName(fn),
                    file_type=FileType(mt),
                )
                attachment_list.append(att)
            # SendGrid Mail.add_attachment prepends (insert index 0), so assigning [A, B] yields [B, A] in the API payload.
            # Reverse so logical order (primary first, then extra_attachments in order) is preserved in the sent email.
            message.attachment = list(reversed(attachment_list))
            response = self.sendgrid_client.send(message)
            ok = response.status_code in [200, 201, 202]
            if ok:
                print(f"[SendGrid] Email with attachment sent OK (status={response.status_code}): to={to_email} subject={subject!r}")
                return (True, None)
            body_preview = (getattr(response, "body", None) or b"").decode("utf-8", errors="replace")[:300]
            msg = f"SendGrid rejected (status {response.status_code}): {body_preview}"
            print(f"[SendGrid] Email with attachment rejected (status={response.status_code}): to={to_email} body={body_preview}")
            return (False, msg)
        except Exception as e:
            msg = str(e) or repr(e)
            print(f"[SendGrid] Error sending email with attachment to {to_email}: {e}")
            return (False, msg)
    
    def send_sms(
        self,
        to_phone: str,
        message: str
    ) -> bool:
        """
        Send SMS using Twilio.
        
        Returns:
            bool indicating success
        """
        if not self.twilio_client or not Config.TWILIO_PHONE_NUMBER:
            print(f"SMS not sent (Twilio not configured): {message} to {to_phone}")
            return False
        
        try:
            message = self.twilio_client.messages.create(
                body=message,
                from_=Config.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            return message.sid is not None
            
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False
