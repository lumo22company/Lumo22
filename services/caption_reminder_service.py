"""
Pre-pack reminder service for 30 Days Captions subscriptions.
Sends email ~5 days before each billing period ends, inviting customers to update intake.
Opt-out by default (reminder_opt_out=false means reminders are ON).
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from config import Config
from services.caption_order_service import CaptionOrderService
from services.notifications import NotificationService

# Days before period end to send reminder
REMINDER_DAYS_BEFORE = 5
# Intake base URL (fallback if Config.BASE_URL has issues)
INTAKE_BASE = "https://lumo-22-production.up.railway.app"


def _safe_base_url() -> str:
    """Base URL for intake links, with fallback."""
    base = (getattr(Config, "BASE_URL", None) or "").strip().rstrip("/")
    base = re.sub(r"[\x00-\x1f\x7f]", "", base) if base else ""
    if base and base.startswith("http"):
        return base
    return INTAKE_BASE


def _should_send_reminder(order: Dict[str, Any], period_end_ts: int) -> bool:
    """True if we should send a reminder for this order and period."""
    if order.get("reminder_opt_out"):
        return False
    sent = order.get("reminder_sent_period_end")
    if sent is None:
        return True
    # Compare as timestamps: if we already sent for this period, skip
    if isinstance(sent, (int, float)):
        return int(sent) != int(period_end_ts)
    if isinstance(sent, str):
        try:
            # Could be ISO or Unix string
            if sent.isdigit():
                return int(sent) != int(period_end_ts)
            dt = datetime.fromisoformat(sent.replace("Z", "+00:00"))
            return int(dt.timestamp()) != int(period_end_ts)
        except (ValueError, TypeError):
            return True
    return True


def run_reminders() -> Dict[str, Any]:
    """
    For each active subscription order:
    - Fetch Stripe subscription current_period_end
    - If ~5 days until period end and not yet reminded for this period, send email
    - Update reminder_sent_period_end
    Returns summary: { "sent": n, "skipped": n, "errors": [...] }
    """
    import stripe

    if not Config.STRIPE_SECRET_KEY:
        return {"sent": 0, "skipped": 0, "errors": ["STRIPE_SECRET_KEY not configured"]}
    stripe.api_key = Config.STRIPE_SECRET_KEY

    order_service = CaptionOrderService()
    notif = NotificationService()
    base = _safe_base_url()
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() + (REMINDER_DAYS_BEFORE * 24 * 60 * 60)
    # We send if period_end is within the next 5–6 days (one-day window so cron doesn't miss)
    window_start = now.timestamp() + (REMINDER_DAYS_BEFORE * 24 * 60 * 60)
    window_end = now.timestamp() + ((REMINDER_DAYS_BEFORE + 1) * 24 * 60 * 60)

    orders = order_service.get_active_subscription_orders()
    sent = 0
    skipped = 0
    errors = []

    for order in orders:
        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            skipped += 1
            continue
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            period_end = sub.get("current_period_end")
            if period_end is None:
                skipped += 1
                continue
            period_end_ts = int(period_end)
            # Only send if period end is in our ~5-day window (avoid sending too early or late)
            if period_end_ts < window_start or period_end_ts > window_end:
                skipped += 1
                continue
            if not _should_send_reminder(order, period_end_ts):
                skipped += 1
                continue

            token = (order.get("token") or "").strip()
            email = (order.get("customer_email") or "").strip()
            if not token or not email or "@" not in email:
                errors.append(f"Order {order.get('id')}: missing token or email")
                skipped += 1
                continue

            intake_url = f"{base}/captions-intake?t={token}"
            account_url = f"{base}/account"
            subject = "Update your captions intake before your next pack"
            body = f"""Hi,

Your next 30 Days of Social Media Captions pack is coming soon. You can update your intake (business details, voice, platforms) anytime before we generate it.

Do you have an event, promotion or something else coming up? Update your intake form to tell us about it and we'll tailor your captions to fit.

Click here to review or update your form:

{intake_url}

This takes about 2 minutes. If you don't change anything, we'll use your existing details.

You can turn these email reminders off in your account: {account_url}

Lumo 22
"""
            ok = notif.send_email(email, subject, body)
            if ok:
                # Store period end as ISO for TIMESTAMPTZ (Postgres)
                period_end_iso = datetime.utcfromtimestamp(period_end_ts).strftime("%Y-%m-%dT%H:%M:%SZ")
                order_service.set_reminder_sent(order["id"], period_end_iso)
                sent += 1
            else:
                errors.append(f"Order {order.get('id')}: email send failed")
                skipped += 1
        except Exception as e:
            errors.append(f"Order {order.get('id')} sub {sub_id[:20]}...: {e}")
            skipped += 1

    return {"sent": sent, "skipped": skipped, "errors": errors}
