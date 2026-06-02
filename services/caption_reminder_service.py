"""
Pre-pack reminder service for 30 Days Captions subscriptions.
Sends email ~5 days before each billing period ends, inviting customers to update intake.
Opt-out by default (reminder_opt_out=false means reminders are ON).

Also sends one-off upgrade reminders: a few days before "day 30" (e.g. 25 or 27 days after
delivery), email one-off customers to offer subscription upgrade. Uses an atomic DB claim on
`upgrade_reminder_sent_at` before send so parallel reminder jobs cannot double-send.

New subscribers: `run_subscription_awaiting_intake_early_reminder` emails once if intake is still
awaiting ~2+ hours after checkout (scheduled every 30 minutes in production; requires DB column
intake_early_reminder_sent_at).

One-off awaiting_intake: `run_reminders` sends a 24–48h gentle reminder once per order using an
atomic DB claim (`one_off_intake_reminder_sent_at`) so overlapping jobs (e.g. daily scheduler + cron)
cannot double-send.
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from urllib.parse import urlencode, quote
from config import Config
from services.caption_order_service import CaptionOrderService, is_sample_pack_order
from services.account_prefill_token import sign_prefill_email
from services.notifications import (
    NotificationService,
    _account_history_notice_upcoming_plain,
    _captions_intake_reminder_email_html,
)

# Days before period end to send reminder
REMINDER_DAYS_BEFORE = 5
# Intake base URL (fallback if Config.BASE_URL has issues)
INTAKE_BASE = "https://lumo-22-production.up.railway.app"
# Subscription checkout → still no intake after this many hours: send one nudge email (idempotent).
SUBSCRIPTION_INTAKE_REMINDER_AFTER_HOURS = 2.0
# Skip very old awaiting_intake rows (e.g. after DB migration adds the tracking column).
SUBSCRIPTION_INTAKE_REMINDER_MAX_ORDER_AGE_HOURS = 168.0


def _pack_cover_line_from_period_end_utc(period_end_ts: int) -> str:
    """Same pack-window sentence as captions intake (ordinal weekdays). Anchor = period end date, floored to today."""
    from api.captions_routes import format_pack_cover_line_ordinal_utc

    anchor = datetime.fromtimestamp(int(period_end_ts), tz=timezone.utc).date()
    today = datetime.now(timezone.utc).date()
    if anchor < today:
        anchor = today
    return format_pack_cover_line_ordinal_utc(anchor) or ""


def _safe_base_url() -> str:
    """Base URL for intake links, with fallback."""
    base = (getattr(Config, "BASE_URL", None) or "").strip().rstrip("/")
    base = re.sub(r"[\x00-\x1f\x7f]", "", base) if base else ""
    if base and base.startswith("http"):
        return base
    return INTAKE_BASE


def _build_one_off_upgrade_url(order: Dict[str, Any]) -> str:
    """Account upgrade hub: same page as Upgrade in the dashboard, with this one-off pre-selected (?base=).

    Customer adjusts platforms / Story Ideas / currency there; checkout gets copy_from + selected + platforms.
    Sign-in is required; unauthenticated clicks go to /login with next= (encoded) to return here.
    Optional ?email= pre-fills login/sign-up with the same address used for the one-off purchase.
    """
    base = _safe_base_url()
    token = (order.get("token") or "").strip()
    if not token:
        return ""
    params: Dict[str, Any] = {"base": token}
    em = (order.get("customer_email") or "").strip().lower()
    if em and "@" in em:
        eph = sign_prefill_email(em)
        if eph:
            params["eph"] = eph
        else:
            params["email"] = em
    return f"{base}/account/upgrade?" + urlencode(params)


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


def _is_subscription_reminder_eligible(sub: Dict[str, Any]) -> bool:
    """True only for subscriptions that are still active and not set to cancel."""
    status = (sub.get("status") or "").strip().lower()
    if status not in ("active", "trialing"):
        return False
    if bool(sub.get("cancel_at_period_end")):
        return False
    if sub.get("canceled_at"):
        return False
    if sub.get("pause_collection"):
        return False
    return True


def _has_other_ready_or_completed_orders(order_service: CaptionOrderService, current_order: Dict[str, Any]) -> bool:
    """
    Suppress awaiting-intake reminders when this customer already has another order that
    is in progress/completed (or already has saved intake/captions).
    """
    email = (current_order.get("customer_email") or "").strip().lower()
    current_id = str(current_order.get("id") or "")
    if not email or "@" not in email:
        return False
    try:
        others = order_service.get_by_customer_email(email)
    except Exception:
        return False
    for o in others:
        oid = str(o.get("id") or "")
        if oid and oid == current_id:
            continue
        status = (o.get("status") or "").strip().lower()
        if status in ("intake_completed", "generating", "delivered", "failed", "hidden"):
            return True
        intake = o.get("intake")
        if isinstance(intake, dict) and len(intake.keys()) > 0:
            return True
        if (o.get("captions_md") or "").strip():
            return True
    return False


def run_subscription_awaiting_intake_early_reminder() -> Dict[str, Any]:
    """
    One email per subscription order: if status is still awaiting_intake and the order is at least
    SUBSCRIPTION_INTAKE_REMINDER_AFTER_HOURS old, send a reminder with the intake link.
    Records intake_early_reminder_sent_at so we never duplicate.
    """
    import stripe

    from api.stripe_utils import is_valid_stripe_subscription_id

    if not getattr(Config, "STRIPE_SECRET_KEY", None) or not str(Config.STRIPE_SECRET_KEY).strip():
        return {"sent": 0, "skipped": 0, "errors": ["STRIPE_SECRET_KEY not configured"]}

    stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
    order_service = CaptionOrderService()
    notif = NotificationService()
    base = _safe_base_url()
    deleted_emails = order_service.get_deleted_account_emails()
    now = datetime.now(timezone.utc)
    sent = 0
    skipped = 0
    errors: List[str] = []

    try:
        awaiting_orders = order_service.get_awaiting_intake_orders()
    except Exception as e:
        return {"sent": 0, "skipped": 0, "errors": [repr(e)]}

    for order in awaiting_orders:
        if (order.get("status") or "").strip().lower() != "awaiting_intake":
            skipped += 1
            continue
        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id or not is_valid_stripe_subscription_id(sub_id):
            skipped += 1
            continue
        if order.get("intake_early_reminder_sent_at"):
            skipped += 1
            continue
        created_raw = order.get("created_at")
        if not created_raw:
            skipped += 1
            continue
        try:
            if isinstance(created_raw, str):
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            else:
                created_dt = created_raw
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
        except Exception:
            skipped += 1
            continue
        age_hours = (now - created_dt).total_seconds() / 3600.0
        if age_hours < SUBSCRIPTION_INTAKE_REMINDER_AFTER_HOURS:
            skipped += 1
            continue
        if age_hours > SUBSCRIPTION_INTAKE_REMINDER_MAX_ORDER_AGE_HOURS:
            skipped += 1
            continue
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            if not _is_subscription_reminder_eligible(sub):
                skipped += 1
                continue
        except Exception as e:
            errors.append(f"Order {order.get('id')} sub {sub_id[:14]}...: {e!r}")
            skipped += 1
            continue

        email = (order.get("customer_email") or "").strip()
        token = (order.get("token") or "").strip()
        if not token or not email or "@" not in email:
            skipped += 1
            continue
        if email.strip().lower() in deleted_emails:
            skipped += 1
            continue

        oid_sub = str(order.get("id") or "").strip()
        if not oid_sub:
            skipped += 1
            continue
        if not order_service.try_claim_intake_early_reminder_sent(oid_sub):
            skipped += 1
            continue

        intake_url = f"{base}/captions-intake?t={token}"
        intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
        business_name = (intake.get("business_name") or "").strip() if intake else ""
        subject = "Complete your form — your subscription is waiting"
        if business_name:
            subject = f"{subject} — {business_name}"
        body = f"""Hi,

{f"Business: {business_name}\n" if business_name else ""}Thanks for subscribing to 30 Days of Social Media Captions.

It has been a couple of hours and we have not received your form yet. We need it before we can generate your first pack.

Complete your form now: {intake_url}

Or copy and paste this link into your browser:

{intake_url}

This takes about 5–10 minutes. Once it is done, we will generate your captions and email your pack—usually within about 15 minutes.

"""
        body = body.rstrip() + "\n\n" + _account_history_notice_upcoming_plain().strip() + "\n\nLumo 22\n"
        html_body = _captions_intake_reminder_email_html(
            intake_url, business_name=business_name or None, variant="subscription_2h"
        )
        try:
            ok = notif.send_email(email, subject, body, html_body=html_body)
        except Exception as e:
            order_service.release_intake_early_reminder_claim(oid_sub)
            errors.append(f"Order {order.get('id')}: subscription early reminder send error: {e!r}")
            skipped += 1
            continue
        if ok:
            sent += 1
        else:
            order_service.release_intake_early_reminder_claim(oid_sub)
            errors.append(f"Order {order.get('id')}: subscription intake reminder send failed")
            skipped += 1

    return {"sent": sent, "skipped": skipped, "errors": errors}


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
    deleted_emails = order_service.get_deleted_account_emails()
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() + (REMINDER_DAYS_BEFORE * 24 * 60 * 60)
    # We send if period_end is within the next 5–6 days (one-day window so cron doesn't miss)
    window_start = now.timestamp() + (REMINDER_DAYS_BEFORE * 24 * 60 * 60)
    window_end = now.timestamp() + ((REMINDER_DAYS_BEFORE + 1) * 24 * 60 * 60)

    orders = order_service.get_active_subscription_orders()
    sent = 0
    skipped = 0
    errors = []

    from api.stripe_utils import is_valid_stripe_subscription_id
    for order in orders:
        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id or not is_valid_stripe_subscription_id(sub_id):
            skipped += 1
            continue
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            if not _is_subscription_reminder_eligible(sub):
                skipped += 1
                continue
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

            period_end_iso = datetime.fromtimestamp(
                period_end_ts, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            old_reminder_sent = order.get("reminder_sent_period_end")
            claim_pre = order_service.try_claim_pre_pack_reminder_sent(str(order["id"]), period_end_iso)
            if claim_pre is False:
                skipped += 1
                continue

            token = (order.get("token") or "").strip()
            email = (order.get("customer_email") or "").strip()
            if not token or not email or "@" not in email:
                errors.append(f"Order {order.get('id')}: missing token or email")
                skipped += 1
                continue
            if email.strip().lower() in deleted_emails:
                skipped += 1
                continue

            intake_url = f"{base}/captions-intake?t={token}"
            intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
            business_name = (intake.get("business_name") or "").strip() if intake else ""
            # Subscribers must log in first; link goes to login with next=form URL so after login they land on the form
            from urllib.parse import quote
            login_url = f"{base}/login?next={quote(intake_url, safe='')}"
            account_url = f"{base}/account"
            subject = "Update your form before your next pack"
            if business_name:
                subject = f"{subject} — {business_name}"
            cover_line = _pack_cover_line_from_period_end_utc(period_end_ts)
            body = f"""Hi,

{f"Business: {business_name}\n" if business_name else ""}{cover_line}

You can update your preferences (business details, voice, platforms) anytime before we generate it.

If you have a launch, event, or promotion within that window, tell us on your form—we will tailor your captions to fit.

Log in to update your form: {login_url}

Or copy and paste this link into your browser. You'll need to log in to your Lumo 22 account first; then you'll be taken to your form.

{login_url}

This takes about 2 minutes. If you don't change anything, we'll use your existing details.

You can turn these reminders off in your account: {account_url}

Lumo 22
"""
            from services.notifications import _captions_reminder_email_html
            html_body = _captions_reminder_email_html(
                login_url,
                account_url,
                business_name=business_name or None,
                next_pack_cover_line=cover_line,
            )
            try:
                ok = notif.send_email(email, subject, body, html_body=html_body)
            except Exception as e:
                errors.append(f"Order {order.get('id')}: pre-pack reminder send error: {e!r}")
                skipped += 1
                if claim_pre is True:
                    order_service.restore_reminder_sent_period_end(str(order["id"]), old_reminder_sent)
                continue
            if ok:
                sent += 1
                if claim_pre is None:
                    order_service.set_reminder_sent(order["id"], period_end_iso)
            else:
                errors.append(f"Order {order.get('id')}: email send failed")
                skipped += 1
                if claim_pre is True:
                    order_service.restore_reminder_sent_period_end(str(order["id"]), old_reminder_sent)
        except Exception as e:
            errors.append(f"Order {order.get('id')} sub {sub_id[:20]}...: {e}")
            skipped += 1

    # One-off: gently remind customers who haven't completed intake yet (awaiting_intake).
    try:
        awaiting_orders = order_service.get_awaiting_intake_orders()
        from datetime import timedelta
        for order in awaiting_orders:
            status = (order.get("status") or "").strip().lower()
            if status != "awaiting_intake":
                continue
            # Subscriptions use run_subscription_awaiting_intake_early_reminder (~2h); skip this 24–48h block.
            if (order.get("stripe_subscription_id") or "").strip():
                skipped += 1
                continue
            # Free 3-caption sample orders must never receive paid-pack reminder copy
            # ("Thanks for your order of 30 Days of Social Media Captions" etc.).
            if is_sample_pack_order(order):
                skipped += 1
                continue
            if _has_other_ready_or_completed_orders(order_service, order):
                skipped += 1
                continue
            email = (order.get("customer_email") or "").strip()
            token = (order.get("token") or "").strip()
            if not token or not email or "@" not in email:
                skipped += 1
                continue
            if email.strip().lower() in deleted_emails:
                skipped += 1
                continue
            created_raw = order.get("created_at")
            if not created_raw:
                skipped += 1
                continue
            try:
                if isinstance(created_raw, str):
                    created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                else:
                    created_dt = created_raw
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
            except Exception:
                skipped += 1
                continue
            age_hours = (now - created_dt).total_seconds() / 3600.0
            # Send a single gentle reminder ~1–2 days after purchase.
            if age_hours < 24.0 or age_hours >= 48.0:
                skipped += 1
                continue
            if order.get("one_off_intake_reminder_sent_at"):
                skipped += 1
                continue
            oid = str(order.get("id") or "").strip()
            if not oid:
                skipped += 1
                continue
            intake_url = f"{base}/captions-intake?t={token}"
            subject = "Complete your form to get your captions"
            intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
            business_name = (intake.get("business_name") or "").strip() if intake else ""
            if business_name:
                subject = f"{subject} — {business_name}"
            body = f"""Hi,

{f"Business: {business_name}\n" if business_name else ""}Thanks for your order of 30 Days of Social Media Captions.

Before we can start writing, we need a few details about your business, audience, and voice.

Complete your form: {intake_url}

Or copy and paste this link into your browser:

{intake_url}

This takes about 5–10 minutes. Once it's done, we'll generate your captions and email your pack.

"""
            body = body.rstrip() + "\n\n" + _account_history_notice_upcoming_plain().strip() + "\n\nLumo 22\n"
            html_body = _captions_intake_reminder_email_html(intake_url, business_name=business_name or None)
            if not order_service.try_claim_one_off_intake_reminder_sent(oid):
                skipped += 1
                continue
            try:
                ok = notif.send_email(email, subject, body, html_body=html_body)
            except Exception as e:
                order_service.release_one_off_intake_reminder_claim(oid)
                errors.append(f"Order {order.get('id')}: intake reminder send error: {e!r}")
                skipped += 1
                continue
            if ok:
                sent += 1
            else:
                order_service.release_one_off_intake_reminder_claim(oid)
                errors.append(f"Order {order.get('id')}: intake reminder email send failed")
                skipped += 1
    except Exception as e:
        errors.append(f"awaiting_intake_reminders: {e}")

    # One-off upgrade reminders: 25 or 27 days after delivery (configurable)
    one_off_upgrade_sent = 0
    try:
        days_before = getattr(Config, "ONE_OFF_UPGRADE_REMINDER_DAYS_BEFORE", 5)
        one_off_orders = order_service.get_one_off_orders_for_upgrade_reminder(days_before_end=days_before)
        base = _safe_base_url()
        notif = NotificationService()
        for order in one_off_orders:
            # Sample-pack rows are never paid one-offs; never send "your 30 days are almost up" upgrade copy.
            if is_sample_pack_order(order):
                skipped += 1
                continue
            email = (order.get("customer_email") or "").strip()
            token = (order.get("token") or "").strip()
            if not email or "@" not in email or not token:
                skipped += 1
                continue
            if email.lower() in deleted_emails:
                skipped += 1
                continue
            upgrade_url = _build_one_off_upgrade_url(order)
            if not upgrade_url:
                errors.append(f"Order {order.get('id')}: could not build upgrade URL")
                skipped += 1
                continue
            unsubscribe_url = f"{base}/api/captions-upgrade-reminder-unsubscribe?t={quote(token)}"
            intake = order.get("intake") or {}
            business_name = (intake.get("business_name") or "").strip() or None
            oid = str(order.get("id") or "").strip()
            if not oid:
                skipped += 1
                continue
            if not order_service.try_claim_upgrade_reminder_sent(oid):
                skipped += 1
                continue
            try:
                ok = notif.send_one_off_upgrade_reminder_email(
                    to_email=email,
                    upgrade_url=upgrade_url,
                    unsubscribe_url=unsubscribe_url,
                    business_name=business_name,
                )
            except Exception as e:
                order_service.release_upgrade_reminder_claim(oid)
                errors.append(f"Order {order.get('id')}: one-off upgrade reminder send error: {e!r}")
                skipped += 1
                continue
            if ok:
                one_off_upgrade_sent += 1
                sent += 1
            else:
                order_service.release_upgrade_reminder_claim(oid)
                errors.append(f"Order {order.get('id')}: one-off upgrade email send failed")
                skipped += 1
    except Exception as e:
        errors.append(f"one_off_upgrade_reminders: {e}")

    return {"sent": sent, "skipped": skipped, "errors": errors, "one_off_upgrade_sent": one_off_upgrade_sent}
