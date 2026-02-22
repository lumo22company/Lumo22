"""
Digital Front Desk: handle inbound emails to forwarding addresses.
SendGrid Inbound Parse POSTs to /webhooks/sendgrid-inbound; we look up the setup,
generate a reply with OpenAI, and send it via SendGrid.
"""
import re
from typing import Optional, Dict, Any
from openai import OpenAI
from config import Config
from services.front_desk_setup_service import FrontDeskSetupService
from services.notifications import NotificationService


def _sanitize_for_email(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text.strip())


TONE_HINTS = {
    "friendly_relaxed": "Friendly and relaxed — casual but still professional.",
    "professional_smart": "Professional and smart — polished, efficient, slightly formal.",
    "warm_reassuring": "Warm and reassuring — empathetic, gentle, supportive.",
    "short_direct": "Short and direct — brief, to the point, minimal flourish.",
}


def generate_reply(
    business_name: str,
    enquiry_email: str,
    booking_link: Optional[str],
    from_email: str,
    subject: str,
    body_plain: str,
    tone: Optional[str] = None,
    reply_style_examples: Optional[str] = None,
    good_lead_rules: Optional[str] = None,
    opening_hours: Optional[str] = None,
    reply_same_day: bool = False,
    reply_24h: bool = False,
) -> str:
    """Use OpenAI to generate a short, professional reply for the business."""
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    system = """You are writing a brief, professional email reply on behalf of a small business (Digital Front Desk).
Use British English. Be helpful, warm, and concise. Do not use emojis or hype.
If a booking link is provided, include it once naturally in the reply. Sign off as the business, not as "AI" or "assistant"."""
    tone_hint = ""
    if tone and tone in TONE_HINTS:
        tone_hint = f"\nTone: {TONE_HINTS[tone]} Match this tone in your reply."
    examples_hint = ""
    if reply_style_examples and reply_style_examples.strip():
        ex = reply_style_examples.strip()[:1500]  # cap length
        examples_hint = f"\nExample replies from this business (match this style and voice):\n---\n{ex}\n---"
    lead_hint = ""
    if good_lead_rules and good_lead_rules.strip():
        lead_hint = f"\nWhen to encourage booking: {good_lead_rules.strip()}. If the enquiry fits, subtly encourage them to book."
    hours_hint = ""
    if opening_hours or reply_same_day or reply_24h:
        parts = []
        if opening_hours:
            parts.append(f"Opening hours: {opening_hours}")
        if reply_same_day:
            parts.append("We usually reply same day.")
        if reply_24h:
            parts.append("We usually reply within 24 hours.")
        hours_hint = f"\nSet expectations: {', '.join(parts)}"
    user = f"""Business name: {business_name}
Enquiry inbox: {enquiry_email}
Booking link: {booking_link or "None"}{tone_hint}{examples_hint}{lead_hint}{hours_hint}

Incoming email from: {from_email}
Subject: {subject}

Body:
{body_plain[:2000]}

Write a single short email reply (2–4 paragraphs max) that the business would send. Output only the reply body, no subject line."""
    try:
        r = client.chat.completions.create(
            model=getattr(Config, "OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=500,
        )
        content = (r.choices[0].message.content or "").strip()
        return _sanitize_for_email(content) if content else ""
    except Exception as e:
        print(f"[inbound-reply] OpenAI error: {e}")
        return ""


def _sender_domain(from_email: str) -> str:
    """Extract lowercase domain from email (e.g. client@gmail.com -> gmail.com)."""
    if not from_email or "@" not in from_email:
        return ""
    return from_email.split("@")[-1].strip().lower()


def _should_skip_reply(setup: Dict[str, Any], from_email: str) -> bool:
    """True if we should not auto-reply (e.g. auto_reply off, or sender domain in skip list)."""
    if setup.get("auto_reply_enabled") is False:
        return True
    skip_domains = (setup.get("skip_reply_domains") or "").strip()
    if not skip_domains:
        return False
    domain = _sender_domain(from_email)
    if not domain:
        return False
    for d in (d.strip().lower() for d in skip_domains.split(",") if d.strip()):
        if d and domain == d:
            return True
    return False


def process_inbound(to_addr: str, from_addr: str, subject: str, text: str, html: str) -> bool:
    """
    Look up Front Desk setup by to_addr (forwarding_email), generate reply, send it.
    Skips if auto_reply_enabled is false or sender domain is in skip_reply_domains.
    Returns True if a reply was sent (or we intentionally skipped; 200 so SendGrid doesn't retry).
    """
    to_addr = (to_addr or "").strip().lower()
    if not to_addr:
        return False
    # SendGrid may send "Name <addr>" or multiple addresses; take first email
    if "<" in to_addr and ">" in to_addr:
        to_addr = to_addr.split("<")[-1].split(">")[0].strip().lower()
    else:
        to_addr = to_addr.split(",")[0].strip().lower()

    svc = FrontDeskSetupService()
    setup = svc.get_by_forwarding_email(to_addr)
    if not setup:
        print(f"[inbound-reply] No setup for to={to_addr}")
        return False

    from_email = (from_addr or "").strip()
    if "<" in from_email and ">" in from_email:
        from_email = from_email.split("<")[-1].split(">")[0].strip()
    else:
        from_email = (from_email.split(",")[0] or "").strip()

    if _should_skip_reply(setup, from_email):
        reason = "auto_reply disabled" if setup.get("auto_reply_enabled") is False else "sender domain in skip list"
        print(f"[inbound-reply] Skipping reply to {from_email} ({reason}) for setup {setup.get('id')}")
        return True  # 200 so SendGrid doesn't retry

    business_name = (setup.get("business_name") or "").strip()
    enquiry_email = (setup.get("enquiry_email") or "").strip()
    booking_link = (setup.get("booking_link") or "").strip() or None
    body_plain = (text or "").strip() or (html or "").replace("<[^>]+>", " ").strip()[:3000]
    tone = (setup.get("tone") or "").strip() or None
    reply_style_examples = (setup.get("reply_style_examples") or "").strip() or None
    good_lead_rules = (setup.get("good_lead_rules") or "").strip() or None
    opening_hours = (setup.get("opening_hours") or "").strip() or None
    reply_same_day = bool(setup.get("reply_same_day"))
    reply_24h = bool(setup.get("reply_24h"))

    reply_body = generate_reply(
        business_name=business_name,
        enquiry_email=enquiry_email,
        booking_link=booking_link,
        from_email=from_email,
        subject=subject or "",
        body_plain=body_plain,
        tone=tone,
        reply_style_examples=reply_style_examples,
        good_lead_rules=good_lead_rules,
        opening_hours=opening_hours,
        reply_same_day=reply_same_day,
        reply_24h=reply_24h,
    )
    if not reply_body:
        print("[inbound-reply] No reply body generated")
        return False

    notif = NotificationService()
    ok = notif.send_email(from_email, subject=f"Re: {subject or 'Your enquiry'}", body=reply_body)
    if ok:
        print(f"[inbound-reply] Sent reply to {from_email} for setup {setup.get('id')}")
    else:
        print(f"[inbound-reply] Failed to send reply to {from_email}")
    return ok
