"""
Notification service for emails and SMS.
Handles automated follow-ups and booking confirmations.
Uses Lumo 22 brand (BRAND_STYLE_GUIDE): black, gold accent, Century Gothic.
"""
import os
import re
from typing import Dict, Any, Optional, Tuple
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
# Use on #fafafa (or similar) panels — muted grey on light grey is hard to read in email clients
BRAND_TEXT_ON_LIGHT_GREY_PANEL = "#000000"
BRAND_TEXT_ON_DARK = "#F5F5F2"
BRAND_FONT = "Century Gothic, CenturyGothic, Apple Gothic, sans-serif"

# Display / composition prices for captions checkout — keep in sync with app.CAPTIONS_DISPLAY_PRICES
_CAPTIONS_DISPLAY_PRICES: Dict[str, Dict[str, Any]] = {
    "gbp": {
        "symbol": "£",
        "oneoff": 97,
        "sub": 79,
        "extra_oneoff": 29,
        "extra_sub": 19,
        "stories_oneoff": 29,
        "stories_sub": 17,
    },
    "usd": {
        "symbol": "$",
        "oneoff": 119,
        "sub": 99,
        "extra_oneoff": 35,
        "extra_sub": 24,
        "stories_oneoff": 35,
        "stories_sub": 21,
    },
    "eur": {
        "symbol": "€",
        "oneoff": 109,
        "sub": 89,
        "extra_oneoff": 32,
        "extra_sub": 22,
        "stories_oneoff": 32,
        "stories_sub": 19,
    },
}


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


def _captions_delivery_review_tip_html(has_stories: bool) -> str:
    """Short tip: review/edit for the month (captions only vs captions + Story Ideas)."""
    if has_stories:
        return (
            f'<p style="margin:0 0 16px; font-size:14px; color:#555;">Tip: read through this month\'s captions and '
            f"Story Ideas before you post. Edit anything so it fits your voice, your brand, and any rules that apply "
            f"to you.</p>"
        )
    return (
        f'<p style="margin:0 0 16px; font-size:14px; color:#555;">Tip: read through this month\'s captions before you '
        f"post. Edit anything so it fits your voice, your brand, and any rules that apply to you.</p>"
    )


def captions_delivery_review_tip_plain(has_stories: bool) -> str:
    """Plain-text review tip for pack delivery email (kept in sync with _captions_delivery_review_tip_html)."""
    if has_stories:
        return (
            "Tip: read through this month's captions and Story Ideas before you post. Edit anything so it fits your "
            "voice, your brand, and any rules that apply to you.\n\n"
        )
    return (
        "Tip: read through this month's captions before you post. Edit anything so it fits your voice, your brand, and "
        "any rules that apply to you.\n\n"
    )


def _pack_sooner_receipt_plain_html(
    order: Dict[str, Any],
    *,
    amount_paid_display: str,
    ongoing_monthly_display: str,
    next_billing_display: Optional[str],
) -> Tuple[str, str]:
    """
    Plain + HTML fragment for get-pack-sooner: one-time charge, current plan (from order — includes
    Update preferences before checkout), ongoing monthly rate, next billing date. Prepended to the
    delivery email so payment confirmation and PDF arrive in one message.
    """
    import html as html_module

    platforms_n = max(1, min(4, int(order.get("platforms_count") or 1)))
    selected = (order.get("selected_platforms") or "").strip()
    if selected:
        platforms_line = selected
    else:
        platforms_line = "1 platform" if platforms_n == 1 else f"{platforms_n} platforms"
    stories_on = bool(order.get("include_stories"))
    stories_line = "30 Days Story Ideas: included" if stories_on else "30 Days Story Ideas: not included"

    nb = (next_billing_display or "").strip()
    safe_amount = html_module.escape((amount_paid_display or "").strip())
    safe_ongoing = html_module.escape((ongoing_monthly_display or "").strip())
    safe_plat = html_module.escape(platforms_line)
    safe_nb = html_module.escape(nb) if nb else ""

    plain = (
        "Get pack sooner — payment received\n"
        f"Amount charged (one-time): {amount_paid_display or '—'}\n\n"
        "Your plan (this pack and going forward)\n"
        f"- Product: 30 Days of Social Media Captions (subscription)\n"
        f"- Platforms: {platforms_line}\n"
        f"- {stories_line}\n"
        f"- Ongoing subscription: {ongoing_monthly_display or '—'}\n"
    )
    if nb:
        plain += f"- Next billing date: {nb}\n"
    plain += "\n"

    rows = (
        f'<p style="margin:0 0 8px;"><strong>Amount charged (one-time):</strong> {safe_amount}</p>'
        f'<p style="margin:0 0 6px; font-size:13px; color:#333;"><strong>Your plan</strong> (this pack and going forward)</p>'
        f'<ul style="margin:0 0 10px; padding-left:18px; font-size:14px; color:#333;">'
        f'<li>30 Days of Social Media Captions (subscription)</li>'
        f'<li>Platforms: {safe_plat}</li>'
        f'<li>{html_module.escape(stories_line)}</li>'
        f'<li>Ongoing subscription: {safe_ongoing}</li>'
        f"{f'<li><strong>Next billing date:</strong> {safe_nb}</li>' if nb else ''}"
        f"</ul>"
    )

    inner = (
        f'<p style="margin:0 0 10px; font-size:15px; color:{BRAND_TEXT}; font-weight:600;">'
        f"Get pack sooner — payment received</p>{rows}"
    )
    html_block = (
        f'<div style="margin:0 0 20px; font-size:14px; color:{BRAND_TEXT_ON_LIGHT_GREY_PANEL}; '
        f'border:1px solid rgba(0,0,0,0.08); border-radius:8px; padding:16px; background:#fafafa;">{inner}</div>'
    )
    return plain, html_block


def _captions_delivery_email_html(
    has_stories: bool,
    has_subscription: bool = False,
    backup_captions_url: str = "",
    backup_stories_url: str = "",
    backup_link_expiry_hours: int = 24,
    business_name: Optional[str] = None,
    next_billing_display: Optional[str] = None,
    pack_sooner_receipt_html: Optional[str] = None,
) -> str:
    """Build explicit HTML for the 30 Days captions delivery email so the body always shows."""
    import html as html_mod

    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    receipt_block = ""
    if (pack_sooner_receipt_html or "").strip():
        receipt_block = (pack_sooner_receipt_html or "").strip()
    intro = '<p style="margin:0 0 16px;">Hi,</p>' + business_line + receipt_block
    if has_stories:
        main = """<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. Both documents are attached.</p>
<p style="margin:0 0 16px;">Copy each caption and story idea as you need them, or edit to fit.</p>"""
    else:
        main = """<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions are ready. The document is attached.</p>
<p style="margin:0 0 16px;">Copy each caption as you need it, or edit to fit.</p>"""
    content = intro + main + _captions_delivery_review_tip_html(has_stories)
    if (next_billing_display or "").strip():
        safe_nb = html_mod.escape((next_billing_display or "").strip(), quote=True)
        content += f"""
<p style="margin:0 0 16px; font-size:15px; color:{BRAND_TEXT};"><strong>Next billing date:</strong> {safe_nb}</p>"""
    if has_subscription:
        content += """
<p style="margin:0 0 16px; font-size:14px; color:#666;">Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account → Manage subscription.</p>"""
    if backup_captions_url:
        safe_captions = backup_captions_url.replace('"', "%22")
        content += f"""
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">If attachments don't appear in your inbox, use your backup download link(s):</p>
<p style="margin:0 0 8px; font-size:13px; color:{BRAND_MUTED};">For your security, these backup links expire within {int(backup_link_expiry_hours)} hour(s).</p>
<p style="margin:0 0 8px;"><a href="{safe_captions}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">Download captions PDF</a></p>"""
        if backup_stories_url:
            safe_stories = backup_stories_url.replace('"', "%22")
            content += f"""
<p style="margin:0 0 16px;"><a href="{safe_stories}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">Download stories PDF</a></p>"""
    content += "\n<p style=\"margin:0;\">— Lumo 22</p>"
    return _email_wrapper(content)


def _captions_reminder_email_html(login_url: str, account_url: str, business_name: Optional[str] = None) -> str:
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
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
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


def _build_captions_order_pricing_detail(
    order: Dict[str, Any],
    currency: str,
    amount_paid_display: Optional[str],
    amount_total_minor: Optional[int],
    *,
    subtotal_minor: Optional[int] = None,
    discount_minor: Optional[int] = None,
    tax_minor: Optional[int] = None,
    discount_label: Optional[str] = None,
    ongoing_monthly_display: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Itemised pack/add-ons (list prices), then Stripe checkout totals when available (subtotal, tax, discount, total).
    discount_label: promotion code(s) or coupon name from Checkout.
    ongoing_monthly_display: full plan price per month for subscriptions (renewals).
    Returns (plain_text, html_fragment) for order confirmation / receipt blocks.
    """
    import html as html_module

    currency = (currency or "gbp").strip().lower()
    p = _CAPTIONS_DISPLAY_PRICES.get(currency, _CAPTIONS_DISPLAY_PRICES["gbp"])
    symbol = str(p["symbol"])
    is_sub = bool((order.get("stripe_subscription_id") or "").strip())
    platforms_n = max(1, min(4, int(order.get("platforms_count") or 1)))
    extras = platforms_n - 1
    stories = bool(order.get("include_stories"))
    selected = (order.get("selected_platforms") or "").strip()
    if selected:
        platforms_line = selected
    else:
        platforms_line = "1 platform" if platforms_n == 1 else f"{platforms_n} platforms"

    plain_lines: list[str] = []
    html_rows: list[str] = []

    def _fmt_money(amount: float, monthly: bool) -> str:
        base = f"{symbol}{amount:.2f}"
        return f"{base}/month" if monthly else base

    if is_sub:
        base_f = float(p["sub"])
        plain_lines.append(f"- Base subscription (includes 1 platform): {_fmt_money(base_f, True)}")
        html_rows.append(
            f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">Base subscription (includes 1 platform)</td>'
            f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(base_f, True))}</td></tr>'
        )
        if extras >= 1:
            extra_unit = float(p["extra_sub"])
            extra_sum = extras * extra_unit
            if extras == 1:
                label = f"Additional platform (1 × {symbol}{extra_unit:.2f})"
            else:
                label = f"Additional platforms ({extras} × {symbol}{extra_unit:.2f})"
            plain_lines.append(f"- {label}: {_fmt_money(extra_sum, True)}")
            html_rows.append(
                f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">{html_module.escape(label)}</td>'
                f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(extra_sum, True))}</td></tr>'
            )
        if stories:
            sf = float(p["stories_sub"])
            plain_lines.append(f"- 30 Days Story Ideas: {_fmt_money(sf, True)}")
            html_rows.append(
                f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">30 Days Story Ideas</td>'
                f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(sf, True))}</td></tr>'
            )
        computed = float(p["sub"]) + extras * float(p["extra_sub"]) + (float(p["stories_sub"]) if stories else 0.0)
    else:
        base_f = float(p["oneoff"])
        plain_lines.append(f"- One-off pack (includes 1 platform): {_fmt_money(base_f, False)}")
        html_rows.append(
            f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">One-off pack (includes 1 platform)</td>'
            f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(base_f, False))}</td></tr>'
        )
        if extras >= 1:
            extra_unit = float(p["extra_oneoff"])
            extra_sum = extras * extra_unit
            if extras == 1:
                label = f"Additional platform (1 × {symbol}{extra_unit:.2f})"
            else:
                label = f"Additional platforms ({extras} × {symbol}{extra_unit:.2f})"
            plain_lines.append(f"- {label}: {_fmt_money(extra_sum, False)}")
            html_rows.append(
                f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">{html_module.escape(label)}</td>'
                f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(extra_sum, False))}</td></tr>'
            )
        if stories:
            sf = float(p["stories_oneoff"])
            plain_lines.append(f"- 30 Days Story Ideas: {_fmt_money(sf, False)}")
            html_rows.append(
                f'<tr><td style="padding:4px 8px 4px 0; vertical-align:top;">30 Days Story Ideas</td>'
                f'<td style="padding:4px 0; text-align:right; white-space:nowrap;">{html_module.escape(_fmt_money(sf, False))}</td></tr>'
            )
        computed = float(p["oneoff"]) + extras * float(p["extra_oneoff"]) + (float(p["stories_oneoff"]) if stories else 0.0)

    computed_minor = int(round(computed * 100))
    plain_lines.append("")

    disc = 0
    if discount_minor is not None:
        try:
            disc = max(0, int(discount_minor))
        except (TypeError, ValueError):
            disc = 0
    tax_amt = 0
    if tax_minor is not None:
        try:
            tax_amt = max(0, int(tax_minor))
        except (TypeError, ValueError):
            tax_amt = 0

    sub_fmt: Optional[str] = None
    if subtotal_minor is not None:
        try:
            sub_fmt = _format_amount_paid(int(subtotal_minor), currency)
        except (TypeError, ValueError):
            sub_fmt = None
    tax_fmt = _format_amount_paid(tax_amt, currency) if tax_amt > 0 else None
    d_fmt = _format_amount_paid(disc, currency) if disc > 0 else None

    show_checkout_totals = bool(amount_paid_display) and bool(sub_fmt or tax_fmt or d_fmt)
    disc_plain_title = "Discount (promotion)"
    if disc > 0 and (discount_label or "").strip():
        disc_plain_title = f"Discount (code / offer: {discount_label.strip()})"
    elif disc > 0:
        disc_plain_title = "Discount (promotion)"

    checkout_extra_html = ""
    if show_checkout_totals:
        plain_lines.extend(["Checkout totals", ""])
        if sub_fmt:
            plain_lines.append(f"Subtotal: {sub_fmt}")
            checkout_extra_html += (
                f'<p style="margin:0 0 6px;"><strong>Subtotal:</strong> '
                f"{html_module.escape(sub_fmt)}</p>"
            )
        if tax_fmt:
            plain_lines.append(f"Tax: {tax_fmt}")
            checkout_extra_html += (
                f'<p style="margin:0 0 6px;"><strong>Tax:</strong> '
                f"{html_module.escape(tax_fmt)}</p>"
            )
        if d_fmt:
            disc_html_title = "Discount (promotion)"
            if (discount_label or "").strip():
                safe_lbl = html_module.escape(discount_label.strip())
                disc_html_title = f"Discount ({safe_lbl})"
            plain_lines.append(f"{disc_plain_title}: −{d_fmt}")
            checkout_extra_html += (
                f'<p style="margin:0 0 6px;"><strong>{disc_html_title}:</strong> '
                f"−{html_module.escape(d_fmt)}</p>"
            )
        plain_lines.append("")

    if amount_paid_display:
        paid_label = "Total paid" if show_checkout_totals else "Amount paid"
        plain_lines.append(f"{paid_label}: {amount_paid_display}")
    elif is_sub:
        plain_lines.append(f"Monthly total (at checkout prices): {_fmt_money(computed, True)}")
    else:
        plain_lines.append(f"Pack total (at checkout prices): {_fmt_money(computed, False)}")

    plain_lines.extend(["", "Your platforms", platforms_line, "", f"Billing: {'Monthly subscription' if is_sub else 'One-off purchase'}"])

    ongoing_html = ""
    if ongoing_monthly_display and is_sub:
        safe_ongoing = html_module.escape(str(ongoing_monthly_display).strip())
        plain_lines.extend(
            [
                "",
                f"Going forward: your subscription renews at {ongoing_monthly_display.strip()} at the plan price.",
                "One-time promotions at checkout usually apply only to this payment; later renewals follow your plan unless you have another active discount in Stripe.",
            ]
        )
        ongoing_html = (
            f'<p style="margin:12px 0 0;"><strong>Going forward:</strong> {safe_ongoing} at the plan price.</p>'
            f'<p style="margin:6px 0 0; font-size:12px; color:{BRAND_MUTED};">'
            "One-time promotions at checkout usually apply only to this payment; renewals follow your plan unless you have another active discount.</p>"
        )

    mismatch_note_plain = ""
    mismatch_note_html = ""
    if (
        amount_paid_display
        and amount_total_minor is not None
        and isinstance(amount_total_minor, (int, float))
        and abs(int(amount_total_minor) - computed_minor) > 2
    ):
        mismatch_note_plain = (
            "\n\n(List prices above may differ from the charged amount if tax, discounts, or proration apply.)"
        )
        mismatch_note_html = (
            f'<p style="margin:10px 0 0; font-size:12px; color:{BRAND_MUTED};">'
            "List prices above may differ from the charged amount if tax, discounts, or proration apply."
            "</p>"
        )

    table_html = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
        f'style="font-size:14px; color:{BRAND_TEXT_ON_LIGHT_GREY_PANEL}; margin:0 0 12px;">'
        + "".join(html_rows)
        + "</table>"
    )
    totals_heading = ""
    if show_checkout_totals:
        totals_heading = (
            f'<p style="margin:12px 0 6px; font-size:13px; color:{BRAND_TEXT_ON_LIGHT_GREY_PANEL};">'
            f"<strong>Checkout totals</strong></p>"
        )
    if amount_paid_display:
        paid_label_html = "Total paid" if show_checkout_totals else "Amount paid"
        total_line = (
            f'<p style="margin:0 0 10px;"><strong>{paid_label_html}:</strong> '
            f"{html_module.escape(amount_paid_display)}</p>"
        )
    elif is_sub:
        total_line = (
            f'<p style="margin:0 0 10px;"><strong>Monthly total (at checkout prices):</strong> '
            f'{html_module.escape(_fmt_money(computed, True))}</p>'
        )
    else:
        total_line = (
            f'<p style="margin:0 0 10px;"><strong>Pack total (at checkout prices):</strong> '
            f'{html_module.escape(_fmt_money(computed, False))}</p>'
        )
    platforms_html = (
        f'<p style="margin:0 0 4px;"><strong>Your platforms</strong></p>'
        f'<p style="margin:0 0 10px; font-size:14px;">{html_module.escape(platforms_line)}</p>'
        f'<p style="margin:0;"><strong>Billing:</strong> '
        f"{'Monthly subscription' if is_sub else 'One-off purchase'}</p>"
    )
    html_fragment = (
        table_html + totals_heading + checkout_extra_html + total_line + platforms_html + ongoing_html + mismatch_note_html
    )
    plain_text = "\n".join(plain_lines) + mismatch_note_plain
    return plain_text, html_fragment


def _extract_business_name(order: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract a display-safe business name from an order dict."""
    if not order or not isinstance(order, dict):
        return None
    intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    raw = (intake.get("business_name") or "").strip()
    safe = _sanitize_email_value(raw)
    return safe or None


def _subject_with_business(subject: str, business_name: Optional[str]) -> str:
    """Append business context to subject for multi-subscription clarity."""
    safe_business = _sanitize_email_value(business_name or "")
    if not safe_business:
        return subject
    return f"{subject} — {safe_business}"


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


def _stripe_session_payment_breakdown(session: Optional[Any]) -> Optional[Dict[str, Any]]:
    """
    Read Stripe Checkout Session amounts for receipt emails.
    Returns dict with currency, subtotal (minor), total (minor), discount (minor), tax (minor).
    """
    if session is None:
        return None

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    curr = str(_get(session, "currency") or "gbp").strip().lower()
    sub = _get(session, "amount_subtotal")
    tot = _get(session, "amount_total")
    td = _get(session, "total_details")
    disc_raw = _get(td, "amount_discount") if td is not None else None

    def _to_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    sub_i = _to_int(sub)
    tot_i = _to_int(tot)
    disc_i = _to_int(disc_raw) or 0
    if disc_i < 0:
        disc_i = 0
    tax_raw = _get(td, "amount_tax") if td is not None else None
    tax_i = _to_int(tax_raw) or 0
    if tax_i < 0:
        tax_i = 0
    return {"currency": curr, "subtotal": sub_i, "total": tot_i, "discount": disc_i, "tax": tax_i}


def _checkout_discount_label_from_session(session: Optional[Any]) -> Optional[str]:
    """Promotion / coupon labels applied at Checkout (comma-separated if several)."""
    if session is None:
        return None

    def _get(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _discount_rows(sess: Any) -> list[Any]:
        raw = _get(sess, "discounts")
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        data = _get(raw, "data")
        if isinstance(data, list):
            return data
        try:
            return list(raw)
        except TypeError:
            return []

    parts: list[str] = []
    for d in _discount_rows(session):
        if d is None:
            continue
        pc = _get(d, "promotion_code")
        if isinstance(pc, dict):
            code = (pc.get("code") or "").strip().upper()
            if code:
                parts.append(code)
                continue
        if pc is not None and not isinstance(pc, str):
            code = str(getattr(pc, "code", "") or "").strip().upper()
            if code:
                parts.append(code)
                continue
        cp = _get(d, "coupon")
        if isinstance(cp, dict):
            name = (cp.get("name") or "").strip()
            cid = (cp.get("id") or "").strip()
            label = name or (f"Coupon ({cid})" if cid else "")
            if label:
                parts.append(label)
        elif cp is not None and not isinstance(cp, str):
            name = str(getattr(cp, "name", "") or "").strip()
            cid = str(getattr(cp, "id", "") or "").strip()
            label = name or (f"Coupon ({cid})" if cid else "")
            if label:
                parts.append(label)

    if parts:
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            k = p.lower()
            if k not in seen:
                seen.add(k)
                out.append(p)
        return ", ".join(out)

    sid = _get(session, "id")
    if sid:
        try:
            from services.stripe_referral_promotion import get_promotion_code_str_from_checkout_session

            code = get_promotion_code_str_from_checkout_session({"id": str(sid)})
            if code:
                return code
        except Exception:
            pass
    return None


def _captions_order_list_price_monthly_display(order: Optional[Dict[str, Any]], currency: str) -> Optional[str]:
    """Full list-price monthly total for a subscription order (before one-time checkout discounts)."""
    if not order or not isinstance(order, dict):
        return None
    if not (order.get("stripe_subscription_id") or "").strip():
        return None
    currency = (currency or "gbp").strip().lower()
    p = _CAPTIONS_DISPLAY_PRICES.get(currency, _CAPTIONS_DISPLAY_PRICES["gbp"])
    symbol = str(p["symbol"])
    platforms_n = max(1, min(4, int(order.get("platforms_count") or 1)))
    extras = platforms_n - 1
    stories = bool(order.get("include_stories"))
    base_f = float(p["sub"])
    computed = base_f + extras * float(p["extra_sub"]) + (float(p["stories_sub"]) if stories else 0.0)
    return f"{symbol}{computed:.2f}/month"


def _checkout_payment_fields_for_order_email(
    order: Optional[Dict[str, Any]],
    session: Optional[Any],
) -> Dict[str, Any]:
    """Stripe checkout amounts + ongoing monthly label for order confirmation emails."""
    currency = (
        str(order.get("currency") or "gbp").strip().lower()
        if order and isinstance(order, dict)
        else "gbp"
    )
    amount_paid: Optional[str] = None
    amount_total_minor: Optional[int] = None
    subtotal_minor: Optional[int] = None
    discount_minor: Optional[int] = None
    tax_minor: Optional[int] = None
    discount_label: Optional[str] = None
    if session:
        amt_raw = session.get("amount_total") if hasattr(session, "get") else getattr(session, "amount_total", None)
        curr_raw = session.get("currency") if hasattr(session, "get") else getattr(session, "currency", "gbp")
        if curr_raw:
            currency = str(curr_raw or "gbp").strip().lower()
        amount_paid = _format_amount_paid(amt_raw, currency)
        if amt_raw is not None and isinstance(amt_raw, (int, float)):
            try:
                amount_total_minor = int(amt_raw)
            except (TypeError, ValueError):
                amount_total_minor = None
        bd = _stripe_session_payment_breakdown(session)
        if bd:
            subtotal_minor = bd.get("subtotal")
            try:
                d0 = int(bd.get("discount") or 0)
                discount_minor = d0 if d0 > 0 else None
            except (TypeError, ValueError):
                discount_minor = None
            try:
                t0 = int(bd.get("tax") or 0)
                tax_minor = t0 if t0 > 0 else None
            except (TypeError, ValueError):
                tax_minor = None
        discount_label = _checkout_discount_label_from_session(session)
    ongoing_monthly: Optional[str] = None
    if order and isinstance(order, dict) and (order.get("stripe_subscription_id") or "").strip():
        ongoing_monthly = _captions_order_list_price_monthly_display(order, currency)
    return {
        "currency": currency,
        "amount_paid": amount_paid,
        "amount_total_minor": amount_total_minor,
        "subtotal_minor": subtotal_minor,
        "discount_minor": discount_minor,
        "tax_minor": tax_minor,
        "discount_label": discount_label,
        "ongoing_monthly": ongoing_monthly,
    }


def _build_subscription_upgrade_pricing_summary(
    order: Optional[Dict[str, Any]], charged_today: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Build text/html pricing summary for one-off -> subscription upgrade emails."""
    import html
    if not order or not isinstance(order, dict):
        return None, None
    currency = str(order.get("currency") or "gbp").strip().lower()
    pr = _CAPTIONS_DISPLAY_PRICES.get(currency, _CAPTIONS_DISPLAY_PRICES["gbp"])
    symbol = str(pr["symbol"])
    base = int(pr["sub"])
    extra = int(pr["extra_sub"])
    stories = int(pr["stories_sub"])
    platforms = max(1, min(4, int(order.get("platforms_count") or 1)))
    stories_included = bool(order.get("include_stories"))
    extras = platforms - 1
    extra_monthly = extras * extra
    platforms_monthly = base + extra_monthly
    stories_monthly = stories if stories_included else 0
    monthly_total = platforms_monthly + stories_monthly
    text_lines = [
        "Upgrade details:",
        f"- Base (includes 1 platform): {symbol}{base}/month",
    ]
    if extras >= 1:
        if extras == 1:
            text_lines.append(
                f"- Additional platform (1 × {symbol}{extra}): {symbol}{extra_monthly}/month"
            )
        else:
            text_lines.append(
                f"- Additional platforms ({extras} × {symbol}{extra}): {symbol}{extra_monthly}/month"
            )
    if stories_included:
        text_lines.append(f"- Story Ideas: {symbol}{stories_monthly}/month")
    else:
        text_lines.append("- Story Ideas: Not included")
    text_lines.append(f"- Monthly total: {symbol}{monthly_total}/month")
    html_lines = [
        "<strong style=\"color:" + BRAND_TEXT + ";\">Upgrade details</strong>",
        f"Base (includes 1 platform): {symbol}{base}/month",
    ]
    if extras >= 1:
        if extras == 1:
            html_lines.append(
                f"Additional platform (1 × {symbol}{extra}): {symbol}{extra_monthly}/month"
            )
        else:
            html_lines.append(
                f"Additional platforms ({extras} × {symbol}{extra}): {symbol}{extra_monthly}/month"
            )
    if stories_included:
        html_lines.append(f"Story Ideas: {symbol}{stories_monthly}/month")
    else:
        html_lines.append("Story Ideas: Not included")
    html_lines.append(f"Monthly total: {symbol}{monthly_total}/month")
    if charged_today:
        text_lines.append(f"- Charged today: {charged_today}")
        html_lines.append(f"Charged today: {html.escape(charged_today)}")
    text_block = "\n".join(text_lines)
    html_block = (
        f"""<p style="margin:0 0 16px; font-size:14px; color:{BRAND_TEXT_ON_LIGHT_GREY_PANEL}; border:1px solid rgba(0,0,0,0.08); """
        f"""border-radius:8px; padding:16px; background:#fafafa;">"""
        + "<br>".join(html_lines)
        + "</p>"
    )
    return text_block, html_block


def _order_receipt_email_html(
    order: Optional[Dict[str, Any]] = None,
    amount_paid: Optional[str] = None,
    amount_total_minor: Optional[int] = None,
    currency: Optional[str] = None,
    business_name: Optional[str] = None,
    *,
    subtotal_minor: Optional[int] = None,
    discount_minor: Optional[int] = None,
    tax_minor: Optional[int] = None,
    discount_label: Optional[str] = None,
    ongoing_monthly_display: Optional[str] = None,
) -> str:
    """Build branded HTML for order receipt — itemised pricing, amount paid, platforms, intake link coming soon."""
    import html as html_module
    receipt_block = ""
    curr = (currency or (order.get("currency") if order else None) or "gbp").strip().lower()
    inner_html = ""
    if order and isinstance(order, dict):
        _, inner_html = _build_captions_order_pricing_detail(
            order,
            curr,
            amount_paid,
            amount_total_minor,
            subtotal_minor=subtotal_minor,
            discount_minor=discount_minor,
            tax_minor=tax_minor,
            discount_label=discount_label,
            ongoing_monthly_display=ongoing_monthly_display,
        )
    elif amount_paid:
        inner_html = f'<p style="margin:0;"><strong>Amount paid:</strong> {html_module.escape(amount_paid)}</p>'
    if inner_html:
        receipt_block = f"""<div style="margin:0 0 16px; font-size:14px; color:{BRAND_TEXT_ON_LIGHT_GREY_PANEL}; border:1px solid rgba(0,0,0,0.08); border-radius:8px; padding:16px; background:#fafafa;"><strong>Order details</strong><br><br>{inner_html}</div>
"""
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
<p style="margin:0 0 16px;">Thanks for your order. We've received your payment for 30 Days of Social Media Captions.</p>
{receipt_block}<p style="margin:0 0 16px;">Complete your short intake form (about 2 minutes) when you're ready. Once you submit, we'll generate your captions and send them to you by email within a few minutes.</p>
<p style="margin:0 0 16px;">If you need the form link again, check your inbox for your order confirmation or reply to this email.</p>
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


def _subscription_welcome_monthly_review_line_html(include_stories: bool) -> str:
    """Expectation-setting: skim/edit each month's pack (captions vs captions + Story Ideas)."""
    if include_stories:
        return (
            f'<p style="margin:0 0 16px; font-size:14px; color:#555;">Each month when your pack arrives by email, '
            f"read through your captions and Story Ideas and edit anything so it fits your brand, your voice, and any "
            f"rules that apply to you before you post.</p>"
        )
    return (
        f'<p style="margin:0 0 16px; font-size:14px; color:#555;">Each month when your pack arrives by email, '
        f"read through your captions and edit anything so it fits your brand, your voice, and any rules that apply to "
        f"you before you post.</p>"
    )


def _subscription_welcome_monthly_review_line_plain(include_stories: bool) -> str:
    """Plain-text version of _subscription_welcome_monthly_review_line_html."""
    if include_stories:
        return (
            "\nEach month when your pack arrives by email, read through your captions and Story Ideas and edit "
            "anything so it fits your brand, your voice, and any rules that apply to you before you post.\n"
        )
    return (
        "\nEach month when your pack arrives by email, read through your captions and edit anything so it fits your "
        "brand, your voice, and any rules that apply to you before you post.\n"
    )


def _subscription_welcome_prefilled_email_html(
    login_url: str,
    intake_url: str,
    pricing_summary_html: Optional[str] = None,
    business_name: Optional[str] = None,
    include_stories: bool = False,
) -> str:
    """Branded HTML for subscription welcome when upgraded from one-off. They already have an account; log in to access prefilled form."""
    import html
    login_url = (login_url or "").strip() or _get_login_url()
    intake_url = (intake_url or "").strip()
    safe_login = html.escape(login_url, quote=True)
    safe_intake = html.escape(intake_url, quote=True) if intake_url and intake_url.startswith("http") else ""
    summary_block = pricing_summary_html or ""
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    review_line = _subscription_welcome_monthly_review_line_html(include_stories)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
<p style="margin:0 0 16px;">You're subscribed to 30 Days of Social Media Captions. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.</p>
{review_line}
{summary_block}
<p style="margin:0 0 24px;"><a href="{safe_login}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Log in to your account</a></p>
<p style="margin:0 0 12px;">Open your form (prefilled); you can edit it anytime in your account:</p>
<p style="margin:0 0 24px;"><a href="{safe_intake}" style="display:inline-block; padding:12px 24px; background:#f0f0f0; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Open your form</a></p>
<p style="margin:0 0 16px;">If you have any questions, just reply to this email.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _subscription_upgrade_confirmation_email_html(
    login_url: str,
    intake_url: str,
    first_charge_date: Optional[str] = None,
    pricing_summary_html: Optional[str] = None,
    business_name: Optional[str] = None,
    include_stories: bool = False,
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
    summary_block = pricing_summary_html or ""
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    review_line = _subscription_welcome_monthly_review_line_html(include_stories)
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
<p style="margin:0 0 16px;">You're set up for your 30 Days Captions subscription. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.</p>
{review_line}
{summary_block}
{charge_p}
<p style="margin:0 0 24px;"><a href="{safe_login}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Log in to your account</a></p>
<p style="margin:0 0 12px;">Open your form (prefilled); you can edit it anytime in your account:</p>
<p style="margin:0 0 24px;"><a href="{safe_intake}" style="display:inline-block; padding:12px 24px; background:#f0f0f0; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Open your form</a></p>
<p style="margin:0 0 16px;">If you have any questions, just reply to this email.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _intake_link_email_html(
    intake_url: str,
    order_summary: Optional[str] = None,
    is_subscription: bool = False,
    business_name: Optional[str] = None,
    order_detail_html: Optional[str] = None,
) -> str:
    """Build branded HTML for captions intake link email — PDF aesthetic, explicit body so it always shows."""
    import html
    intake_url = (intake_url or "").strip()
    if not intake_url or not intake_url.startswith("http"):
        intake_url = ""
    safe_url = html.escape(intake_url, quote=True)
    login_url = _get_login_url()
    safe_login = html.escape(login_url, quote=True)
    summary_block = ""
    if order_detail_html and str(order_detail_html).strip():
        summary_block = f"""<div style="margin:0 0 16px; font-size:14px; line-height:1.6; color:{BRAND_BLACK};"><strong>Order summary</strong><br><br>{order_detail_html.strip()}</div>
"""
    elif order_summary and order_summary.strip():
        summary_escaped = html.escape(order_summary.strip()).replace("\n", "<br>\n")
        summary_block = f"""<p style="margin:0 0 16px; font-size:14px; line-height:1.6; color:{BRAND_BLACK};"><strong>Order summary</strong><br><br>{summary_escaped}</p>
"""
    account_line = "On the form you can also create an account to access your captions and manage your subscription in one place." if is_subscription else "On the form you can also create an account to access your captions in one place."
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
<p style="margin:0 0 16px;">We've received your payment — thank you. Your 30 Days of Social Media Captions will be tailored to your business and voice.</p>
{summary_block}<p style="margin:0 0 12px;">Next step: complete this short form so we can create your captions. It takes about 2 minutes.</p>
<p style="margin:0 0 12px; font-size:14px; color:{BRAND_MUTED};"><strong style="color:{BRAND_TEXT};">For security:</strong> If you already have a Lumo 22 account, <a href="{safe_login}" style="color:{BRAND_BLACK}; text-decoration:none; border-bottom:1px solid {BRAND_BLACK};">log in first</a>, then use the button below to open your form.</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Complete the form</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy and paste this link into your browser:</p>
<p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
<p style="margin:0 0 16px;">Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.</p>
<p style="margin:0 0 16px;">{html.escape(account_line)}</p>
<p style="margin:0 0 16px;">Thanks for choosing us.</p>
<p style="margin:0;">— Lumo 22</p>"""
    return _email_wrapper(content)


def _captions_intake_reminder_email_html(intake_url: str, business_name: Optional[str] = None) -> str:
    """Branded HTML for one-off intake reminder (customer hasn't completed form yet)."""
    import html
    intake_url = (intake_url or "").strip()
    if not intake_url or not intake_url.startswith("http"):
        intake_url = ""
    safe_url = html.escape(intake_url, quote=True)
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
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
    business_name: Optional[str] = None,
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
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
<p style="margin:0 0 16px;">Your 30 Days of Social Media Captions subscription has been cancelled.</p>
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
    business_name: Optional[str] = None,
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
    business_line = ""
    safe_business = _sanitize_email_value(business_name or "")
    if safe_business:
        business_line = f"<p style=\"margin:0 0 16px;\"><strong>Business:</strong> {safe_business}</p>"
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
{business_line}
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


def _referral_referrer_reward_email_html(account_refer_url: str, credits_total: int) -> str:
    """Email to referrer when a friend’s purchase earns them a referral credit."""
    import html

    safe_url = html.escape(account_refer_url, quote=True)
    if credits_total <= 1:
        credits_line = (
            "You have <strong>1</strong> referral credit — 10% off your next captions subscription billing period."
        )
    else:
        credits_line = (
            f"You now have <strong>{credits_total}</strong> referral credits — 10% off your next "
            f"{credits_total} billing periods (one discount per period)."
        )
    content = f"""<p style="margin:0 0 16px;">Hi,</p>
<p style="margin:0 0 16px;">Good news — someone completed a qualifying captions purchase through your referral. We've added a referral credit to your account.</p>
<p style="margin:0 0 16px;">{credits_line}</p>
<p style="margin:0 0 16px;">View your credits and share your code anytime:</p>
<p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:14px 28px; background:{BRAND_GOLD}; color:{BRAND_BLACK}; text-decoration:none; border-radius:10px; font-weight:600;">Refer a friend</a></p>
<p style="margin:0 0 8px; font-size:14px; color:{BRAND_MUTED};">Or copy this link:</p>
<p style="margin:0 0 16px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
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

    def send_referral_referrer_reward_email(
        self, to_email: str, account_refer_url: str, credits_total: int
    ) -> bool:
        """Notify referrer that a qualifying purchase earned them a credit (signup ref and/or code at checkout)."""
        account_refer_url = (account_refer_url or "").strip()
        if not account_refer_url.startswith("http"):
            print("[SendGrid] Referral reward email NOT sent: invalid account_refer_url")
            return False
        credits_total = max(1, int(credits_total or 1))
        subject = "You earned a Lumo 22 referral credit"
        if credits_total == 1:
            credits_plain = (
                "You have 1 referral credit — 10% off your next captions subscription billing period."
            )
        else:
            credits_plain = (
                f"You now have {credits_total} referral credits — 10% off your next {credits_total} "
                "billing periods (one discount per period)."
            )
        body = f"""Hi,

Good news — someone completed a qualifying captions purchase through your referral. We've added a referral credit to your account.

{credits_plain}

View your credits and share your code anytime:
{account_refer_url}

— Lumo 22
"""
        html_body = _referral_referrer_reward_email_html(account_refer_url, credits_total)
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
        business_name: Optional[str] = None,
    ) -> bool:
        """Send confirmation when customer upgrades, downgrades, or adds Stories."""
        safe_business = _sanitize_email_value(business_name or "")
        subject = _subject_with_business("Your Lumo 22 plan has been updated", safe_business or None)
        price_block = ""
        if new_price_display:
            if old_price_display:
                price_block = f"\nNew price: {new_price_display}/month (was {old_price_display}/month).\n"
            else:
                price_block = f"\nNew price: {new_price_display}/month.\n"
        business_line = f"Business: {safe_business}\n\n" if safe_business else ""
        body = f"""Hi,

You made changes to your Lumo 22 subscription.
{business_line}

{change_summary or "Your plan has been updated."}
{price_block}
When does this take effect? {when_effective or "Changes apply to your next pack."}

You can manage your subscription anytime in your account: {account_url or ""}

— Lumo 22"""
        html_body = _plan_change_confirmation_email_html(
            change_summary, when_effective, account_url,
            new_price_display=new_price_display,
            old_price_display=old_price_display,
            business_name=safe_business or None,
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_cancelled_email(
        self,
        to_email: str,
        captions_url: str,
        plan_summary: str | None = None,
        price_display: str | None = None,
        business_name: Optional[str] = None,
    ) -> bool:
        """Send confirmation when customer cancels their subscription."""
        safe_business = _sanitize_email_value(business_name or "")
        subject = _subject_with_business("Your subscription has been cancelled", safe_business or None)
        summary_block = ""
        if plan_summary or price_display:
            parts = []
            if plan_summary:
                parts.append(plan_summary)
            if price_display:
                parts.append(price_display)
            summary_block = f"\n\nWhat you cancelled: {' — '.join(parts)}\n"
        business_line = f"\nBusiness: {safe_business}\n" if safe_business else ""
        body = f"""Hi,

Your 30 Days of Social Media Captions subscription has been cancelled.{business_line}{summary_block}
We're sorry to see you go. If you change your mind, you can subscribe again anytime at {captions_url or "lumo22.com/captions"}.

— Lumo 22"""
        html_body = _subscription_cancelled_email_html(
            captions_url, plan_summary=plan_summary, price_display=price_display, business_name=safe_business or None
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
        """Standalone receipt (payment + order lines). Not sent after normal checkout — use send_intake_link_email with session instead.
        Kept for manual resend, tests, and samples. order: caption order dict. session: Stripe checkout session for amount_paid."""
        business_name = _extract_business_name(order) if order else None
        subject = _subject_with_business("Thanks for your order — 30 Days of Social Media Captions", business_name)
        pay = _checkout_payment_fields_for_order_email(order if isinstance(order, dict) else None, session)
        currency = pay["currency"]
        amount_paid = pay["amount_paid"]
        amount_total_minor = pay["amount_total_minor"]
        subtotal_minor = pay["subtotal_minor"]
        discount_minor = pay["discount_minor"]
        tax_minor = pay["tax_minor"]
        discount_label = pay["discount_label"]
        ongoing_monthly = pay["ongoing_monthly"]

        receipt_plain = ""
        if order and isinstance(order, dict):
            receipt_plain, _ = _build_captions_order_pricing_detail(
                order,
                currency,
                amount_paid,
                amount_total_minor,
                subtotal_minor=subtotal_minor,
                discount_minor=discount_minor,
                tax_minor=tax_minor,
                discount_label=discount_label,
                ongoing_monthly_display=ongoing_monthly,
            )

        body_lines = [
            "Hi,",
            "",
        ]
        if business_name:
            body_lines.extend([f"Business: {business_name}", ""])
        body_lines.extend([
            "Thanks for your order. We've received your payment for 30 Days of Social Media Captions.",
            "",
        ])
        if receipt_plain:
            body_lines.append("Order details:")
            body_lines.append(receipt_plain)
            body_lines.extend(["", ""])
        elif amount_paid:
            body_lines.append("Order details:")
            body_lines.append(f"Amount paid: {amount_paid}")
            body_lines.extend(["", ""])
        body_lines.extend([
            "Complete your short intake form (about 2 minutes) when you're ready. "
            "Once you submit, we'll generate your captions and send them to you by email within a few minutes.",
            "",
            "If you need the form link again, check your inbox for your order confirmation or reply to this email.",
            "",
            "— Lumo 22",
        ])
        body = "\n".join(body_lines)
        html_body = _order_receipt_email_html(
            order=order if isinstance(order, dict) else None,
            amount_paid=amount_paid,
            amount_total_minor=amount_total_minor,
            currency=currency,
            business_name=business_name,
            subtotal_minor=subtotal_minor,
            discount_minor=discount_minor,
            tax_minor=tax_minor,
            discount_label=discount_label,
            ongoing_monthly_display=ongoing_monthly,
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_intake_link_email(
        self,
        to_email: str,
        intake_url: str,
        order: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None,
    ) -> bool:
        """Send single post-checkout email: payment confirmation, order summary (with Stripe session when provided), and intake link."""
        if not intake_url or not str(intake_url).strip().startswith("http"):
            print("[SendGrid] Intake link email NOT sent: invalid intake_url")
            return False
        business_name = _extract_business_name(order) if order else None
        subject = _subject_with_business("Order confirmed — 30 Days of Social Media Captions (next step)", business_name)
        pay = _checkout_payment_fields_for_order_email(order if isinstance(order, dict) else None, session)
        curr = pay["currency"]
        order_detail_plain: Optional[str] = None
        order_detail_html: Optional[str] = None
        if order and isinstance(order, dict):
            order_detail_plain, order_detail_html = _build_captions_order_pricing_detail(
                order,
                curr,
                pay["amount_paid"],
                pay["amount_total_minor"],
                subtotal_minor=pay["subtotal_minor"],
                discount_minor=pay["discount_minor"],
                tax_minor=pay["tax_minor"],
                discount_label=pay["discount_label"],
                ongoing_monthly_display=pay["ongoing_monthly"],
            )
        body = "Hi,\n\nWe've received your payment — thank you. Your 30 Days of Social Media Captions will be tailored to your business and voice.\n\n"
        if business_name:
            body = f"Hi,\n\nBusiness: {business_name}\n\nWe've received your payment — thank you. Your 30 Days of Social Media Captions will be tailored to your business and voice.\n\n"
        if order_detail_plain:
            body += "Order summary\n" + order_detail_plain + "\n\n"
        body += "Next step: complete this short form so we can create your captions. It takes about 2 minutes.\n\n"
        base = (Config.BASE_URL or "").strip().rstrip("/")
        login_url = f"{base}/login" if base and base.startswith("http") else "https://www.lumo22.com/login"
        body += "For security: If you already have a Lumo 22 account, log in first (" + login_url + "), then use the link below to open your form.\n\n"
        body += intake_url
        is_sub = bool(order and (order.get("stripe_subscription_id") or "").strip())
        account_line = "On the form you can also create an account to access your captions and manage your subscription in one place." if is_sub else "On the form you can also create an account to access your captions in one place."
        body += "\n\nOnce you submit, we'll generate your 30 captions and send them to you by email within a few minutes.\n\n" + account_line + "\n\nThanks for choosing us.\n\nLumo 22"
        html_body = _intake_link_email_html(
            intake_url,
            order_summary=None,
            is_subscription=is_sub,
            business_name=business_name,
            order_detail_html=order_detail_html,
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_welcome_prefilled_email(
        self, to_email: str, intake_url: str, order: Optional[Dict[str, Any]] = None, amount_paid: Optional[str] = None
    ) -> bool:
        """Send welcome email when customer upgraded from one-off to subscription (and was charged at checkout, e.g. get pack now). Form is prefilled."""
        if not to_email or "@" not in str(to_email):
            return False
        business_name = _extract_business_name(order) if order else None
        include_stories = bool(order and order.get("include_stories"))
        subject = _subject_with_business("You're subscribed — 30 Days Captions", business_name)
        login_url = _get_login_url()
        pricing_text, pricing_html = _build_subscription_upgrade_pricing_summary(order, charged_today=amount_paid)
        pricing_block = ("\n\n" + pricing_text + "\n") if pricing_text else ""
        review_plain = _subscription_welcome_monthly_review_line_plain(include_stories)
        body = """Hi,

You're subscribed to 30 Days of Social Media Captions. Your form is already filled from your one-off pack—log in to your account to review or edit it whenever you like.
""" + review_plain + pricing_block + """
Log in to your account: """ + login_url + """

Open your form (prefilled); you can edit it anytime in your account: """ + (intake_url or "") + """

If you have any questions, just reply to this email.

— Lumo 22
"""
        if business_name:
            body = body.replace("Hi,\n\n", f"Hi,\n\nBusiness: {business_name}\n\n", 1)
        html_body = _subscription_welcome_prefilled_email_html(
            login_url,
            intake_url,
            pricing_summary_html=pricing_html,
            business_name=business_name,
            include_stories=include_stories,
        )
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_subscription_upgrade_confirmation_email(
        self, to_email: str, intake_url: str, first_charge_date: Optional[str] = None, order: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Confirmation when customer upgraded from one-off to subscription with trial (no charge today). You'll be charged when first pack is ready."""
        if not to_email or "@" not in str(to_email):
            return False
        business_name = _extract_business_name(order) if order else None
        include_stories = bool(order and order.get("include_stories"))
        subject = _subject_with_business("You're set up — 30 Days Captions subscription", business_name)
        login_url = _get_login_url()
        pricing_text, pricing_html = _build_subscription_upgrade_pricing_summary(order)
        pricing_block = ("\n\n" + pricing_text) if pricing_text else ""
        review_plain = _subscription_welcome_monthly_review_line_plain(include_stories)
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
""" + review_plain + pricing_block + """
""" + charge_line + """
Log in to your account: """ + login_url + """

Open your form (prefilled); you can edit it anytime in your account: """ + (intake_url or "") + """

If you have any questions, just reply to this email.

— Lumo 22
"""
        if business_name:
            body = body.replace("Hi,\n\n", f"Hi,\n\nBusiness: {business_name}\n\n", 1)
        html_body = _subscription_upgrade_confirmation_email_html(
            login_url,
            intake_url,
            first_charge_date,
            pricing_summary_html=pricing_html,
            business_name=business_name,
            include_stories=include_stories,
        )
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
        subject = _subject_with_business("Your 30 days of captions — upgrade to a subscription?", business_name)
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
            err_s = str(e).lower()
            if "401" in err_s or "unauthorized" in err_s:
                print(
                    "[SendGrid] Email NOT sent (401 Unauthorized): SENDGRID_API_KEY is missing, revoked, or wrong. "
                    "Create a new key at https://app.sendgrid.com/settings/api_keys and set it in Railway."
                )
            else:
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
