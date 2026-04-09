"""
API routes for 30 Days Captions: checkout (redirect to intake after payment), intake submission, intake-link lookup.

Subscription (£79/mo) vs one-off (£97): same intake form and delivery flow; subscription uses Stripe
mode=subscription and is detected in webhook so we create order and send intake email on first payment.
"""
import os
import time
import threading
import hmac
import hashlib
import base64
from typing import Any, Optional
from flask import Blueprint, request, jsonify, redirect, Response, url_for
from urllib.parse import quote
from config import Config

captions_bp = Blueprint("captions", __name__, url_prefix="/api")

_email_change_attempts = {}
_email_change_resend_last = {}


def _get_referral_coupon_id():
    """
    Legacy: auto-applied coupon on Checkout Session. Refer-a-friend now uses Stripe Promotion Codes
    (one per referrer) entered on the Stripe payment page — see allow_promotion_codes on Session.create.
    Kept for tests and optional call sites; captions checkout no longer applies this automatically.
    """
    coupon_id = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
    if not coupon_id:
        return None
    ref = (request.args.get("ref") or "").strip()
    if ref:
        from services.customer_auth_service import CustomerAuthService
        if CustomerAuthService().get_by_referral_code(ref):
            return coupon_id
    from api.auth_routes import get_current_customer
    customer = get_current_customer()
    if customer and customer.get("referred_by_customer_id"):
        return coupon_id
    return None


def _parse_platforms(request) -> int:
    """Parse platforms query param; clamp to 1–4. Default 1."""
    try:
        n = int(request.args.get("platforms", 1))
        return max(1, min(4, n))
    except (TypeError, ValueError):
        return 1


def _parse_selected_platforms(request):
    # Returns str or None
    """Parse selected platforms from query (e.g. selected=Instagram,LinkedIn). Max 200 chars for Stripe metadata."""
    raw = (request.args.get("selected") or request.args.get("selected_platforms") or "").strip()
    if not raw:
        return None
    return raw[:200] or None


def _parse_stories(request) -> bool:
    """True when ?stories=1 or stories=true (Stories add-on selected)."""
    v = request.args.get("stories", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _parse_currency(request) -> str:
    """Return currency from ?currency= (gbp, usd, eur). Default gbp. Used for checkout and display."""
    v = (request.args.get("currency") or "").strip().lower()
    if v in ("usd", "eur"):
        return v
    return "gbp"


def _parse_checkout_email(request):
    """
    Parse checkout email fields from query params.
    Returns (email, error). Email is normalized lowercase when valid.
    """
    email = (request.args.get("email") or "").strip().lower()
    email_confirm = (request.args.get("email_confirm") or "").strip().lower()
    if not email and not email_confirm:
        return None, None
    if not email or "@" not in email:
        return None, "Please enter a valid email."
    if email != email_confirm:
        return None, "Email addresses do not match."
    return email, None


def _recovery_secret_bytes() -> bytes:
    return ((getattr(Config, "SECRET_KEY", None) or "").strip() or "dev-recovery-secret").encode("utf-8")


def _make_email_recovery_token(order_id: str, session_id: str, ts: Optional[int] = None) -> str:
    ts = int(ts or time.time())
    payload = f"{order_id}:{session_id}:{ts}"
    sig = hmac.new(_recovery_secret_bytes(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _verify_email_recovery_token(token: str, order_id: str, session_id: str, *, max_age_seconds: int = 1800) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) < 4:
            return False
        tok_order_id = parts[0]
        tok_session_id = parts[1]
        tok_ts = int(parts[2])
        tok_sig = parts[3]
    except Exception:
        return False
    if tok_order_id != str(order_id) or tok_session_id != str(session_id):
        return False
    if int(time.time()) - tok_ts > max_age_seconds:
        return False
    payload = f"{tok_order_id}:{tok_session_id}:{tok_ts}"
    expected = hmac.new(_recovery_secret_bytes(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(tok_sig, expected)


def _email_change_allowed(order_id: str, ip: str) -> bool:
    now = time.time()
    key = f"{order_id}:{ip or 'unknown'}"
    attempts = [t for t in (_email_change_attempts.get(key) or []) if now - t <= 3600]
    if len(attempts) >= 3:
        _email_change_attempts[key] = attempts
        return False
    attempts.append(now)
    _email_change_attempts[key] = attempts
    return True


def _email_resend_allowed(order_id: str, *, cooldown_seconds: int = 300) -> bool:
    now = time.time()
    last = float(_email_change_resend_last.get(str(order_id), 0) or 0)
    if now - last < cooldown_seconds:
        return False
    _email_change_resend_last[str(order_id)] = now
    return True


def _public_download_expiry_seconds() -> int:
    try:
        raw = int(os.getenv("CAPTIONS_PUBLIC_DOWNLOAD_LINK_TTL_SECONDS", "86400"))  # 24h default
        return max(300, min(raw, 1209600))  # clamp 5 min .. 14 days
    except Exception:
        return 86400


def _public_download_expiry_hours() -> int:
    secs = _public_download_expiry_seconds()
    return max(1, int((secs + 3599) // 3600))


def _make_public_download_sig(token: str, file_type: str, exp_ts: int) -> str:
    payload = f"{token}:{file_type}:{int(exp_ts)}"
    return hmac.new(_recovery_secret_bytes(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_public_download_url(base: str, token: str, file_type: str) -> str:
    t = (token or "").strip()
    ft = (file_type or "captions").strip().lower()
    exp_ts = int(time.time()) + _public_download_expiry_seconds()
    sig = _make_public_download_sig(t, ft, exp_ts)
    return f"{base}/api/captions-download-public?t={quote(t)}&type={quote(ft)}&exp={exp_ts}&sig={quote(sig)}"


def _verify_public_download_signature(token: str, file_type: str, exp_ts: int, sig: str) -> bool:
    if not token or not sig:
        return False
    if int(exp_ts) < int(time.time()):
        return False
    expected = _make_public_download_sig(token, file_type, int(exp_ts))
    return hmac.compare_digest((sig or "").strip(), expected)


def _append_email_change_event(order_service, order: dict, *, old_email: str, new_email: str, ip: str, user_agent: str) -> None:
    """
    Best-effort audit trail for corrected checkout emails.
    Persists to caption_orders.email_change_events when the column exists.
    """
    try:
        order_id = str(order.get("id") or "").strip()
        if not order_id:
            return
        current_events = order.get("email_change_events") or []
        if not isinstance(current_events, list):
            current_events = []
        event = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "old_email": (old_email or "").strip().lower() or None,
            "new_email": (new_email or "").strip().lower() or None,
            "ip": (ip or "").strip() or None,
            "user_agent": (user_agent or "").strip()[:300] or None,
            "source": "thank_you_wrong_email",
        }
        current_events.append(event)
        # Keep only the latest 20 events.
        if len(current_events) > 20:
            current_events = current_events[-20:]
        order_service.update(order_id, {"email_change_events": current_events})
    except Exception as e:
        # Non-fatal by design (e.g. column not migrated yet).
        print(f"[captions-correct-email] audit event write skipped: {e!r}")


def _base_url_for_redirect() -> str:
    """Base URL for Stripe success/cancel redirects. Prefer www for lumo22.com so redirect lands on the host that serves the app."""
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base:
        return base
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    # If BASE_URL is bare lumo22.com, use www so Stripe redirects to the host that serves the app (avoids 404)
    if base in ("https://lumo22.com", "http://lumo22.com"):
        return "https://www.lumo22.com"
    return base


def _filename_safe(s: str, max_len: int = 50) -> str:
    """Sanitize string for PDF filename: alphanumeric, spaces to underscores, remove other chars."""
    if not s or not isinstance(s, str):
        return ""
    s = s.strip()
    out = []
    for c in s:
        if c.isalnum() or c in " -_":
            out.append(c if c != " " else "_")
    result = "".join(out).strip("_").replace("__", "_")[:max_len]
    return result if result else ""


# Amounts in smallest unit (pence/cents) for add-ons when using price_data (USD/EUR). GBP add-ons use existing Price IDs.
_CURRENCY_ADDON_AMOUNTS = {
    "gbp": {"extra_oneoff": 2900, "extra_sub": 1900, "stories_oneoff": 2900, "stories_sub": 1700},
    "usd": {"extra_oneoff": 3500, "extra_sub": 2400, "stories_oneoff": 3500, "stories_sub": 2100},
    "eur": {"extra_oneoff": 3200, "extra_sub": 2200, "stories_oneoff": 3200, "stories_sub": 1900},
}

# Display prices (symbol + sub amounts) for Stripe custom_text — must match app.CAPTIONS_DISPLAY_PRICES
_DISPLAY_PRICES = {
    "gbp": {"symbol": "£", "sub": 79, "extra_sub": 19, "stories_sub": 17},
    "usd": {"symbol": "$", "sub": 99, "extra_sub": 24, "stories_sub": 21},
    "eur": {"symbol": "€", "sub": 89, "extra_sub": 22, "stories_sub": 19},
}

def _get_base_price_id(currency: str) -> str:
    """Return Stripe Price ID for captions one-off in the given currency. Raises if not configured."""
    if currency == "gbp":
        pid = Config.STRIPE_CAPTIONS_PRICE_ID
    elif currency == "usd":
        pid = getattr(Config, "STRIPE_CAPTIONS_PRICE_ID_USD", None) or ""
    else:
        pid = getattr(Config, "STRIPE_CAPTIONS_PRICE_ID_EUR", None) or ""
    pid = (pid or "").strip()
    if not pid:
        return (Config.STRIPE_CAPTIONS_PRICE_ID or "").strip() or None  # fallback to GBP
    return pid


def _get_sub_price_id(currency: str) -> str:
    """Return Stripe Price ID for captions subscription in the given currency."""
    if currency == "gbp":
        pid = getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or ""
    elif currency == "usd":
        pid = getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or ""
    else:
        pid = getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or ""
    pid = (pid or "").strip()
    if not pid and currency != "gbp":
        pid = (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    return pid or None


def _normalize_error(err) -> str:
    """Turn any error from generation/delivery into a short ASCII string for JSON."""
    if err is None:
        return "Unknown error"
    if isinstance(err, str):
        out = err.strip() or "Unknown error"
    elif isinstance(err, dict):
        out = err.get("message") or (err.get("error") or {}).get("message") if isinstance(err.get("error"), dict) else err.get("error")
        out = str(out).strip() if out else "Unknown error"
    else:
        out = str(err).strip() or repr(err) or "Unknown error"
    out = (out or "Unknown error")[:500]
    return "".join(c for c in out if ord(c) < 128)


def _captions_subscription_base_price_ids() -> set:
    """Stripe price IDs for the monthly Captions base subscription (all currencies)."""
    out = set()
    for key in (
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID",
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD",
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR",
    ):
        pid = (getattr(Config, key, None) or "").strip()
        if pid:
            out.add(pid)
    return out


def _stripe_subscription_has_captions_base_price(sub_obj: dict) -> bool:
    """True if subscription line items include a Captions base monthly price."""
    base_ids = _captions_subscription_base_price_ids()
    if not base_ids:
        return False
    items = sub_obj.get("items") or {}
    if isinstance(items, dict):
        items = items.get("data") or []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        price = item.get("price") or {}
        pid = price.get("id") if isinstance(price, dict) else None
        if pid and pid in base_ids:
            return True
    return False


def _stripe_subscription_blocks_new_checkout(sub_obj: dict) -> bool:
    """True if this Captions subscription is active enough that we should not start another checkout."""
    if not _stripe_subscription_has_captions_base_price(sub_obj):
        return False
    status = (sub_obj.get("status") or "").strip()
    if status in ("canceled", "unpaid", "incomplete_expired", "incomplete"):
        return False
    return status in ("active", "trialing", "past_due")


def _normalize_business_key(value: str) -> str:
    """Normalize business identifier for matching (lowercase, alnum + single hyphens)."""
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    out = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def seed_intake_business_from_stripe_metadata(order_service, order: dict, meta) -> dict:
    """
    If Stripe checkout metadata includes business_name or business_key, merge intake.business_name early
    so receipt and intake emails can show the brand. Does not overwrite an existing intake.business_name.
    """
    if not order or not isinstance(order, dict):
        return order
    oid = order.get("id")
    if not oid:
        return order
    intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    if (intake.get("business_name") or "").strip():
        return order
    if isinstance(meta, dict):
        md = meta
    elif meta is not None and hasattr(meta, "get"):
        md = {"business_name": meta.get("business_name"), "business_key": meta.get("business_key")}
    else:
        md = {}
    business_name = (md.get("business_name") or "").strip() or None
    business_key = _normalize_business_key((md.get("business_key") or "").strip())
    if not business_name and business_key:
        business_name = business_key.replace("-", " ").title()
    if not business_name:
        return order
    name = business_name[:120]
    merged = dict(intake or {})
    merged["business_name"] = name
    try:
        order_service.update_intake_only(str(oid), merged)
        return order_service.get_by_id(str(oid)) or {**order, "intake": merged}
    except Exception:
        return {**order, "intake": merged}


def enrich_order_intake_from_checkout_session(order_service, order: dict) -> dict:
    """
    If intake has no business_name yet, load Stripe Checkout Session metadata and seed intake.
    Covers the race where the customer opens the intake link before the payment webhook has run.
    """
    if not order or not isinstance(order, dict):
        return order
    intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    if (intake.get("business_name") or "").strip():
        return order
    sid = (order.get("stripe_session_id") or "").strip()
    if not sid:
        return order
    try:
        import stripe

        if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
            return order
        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
        session = stripe.checkout.Session.retrieve(sid)
        meta = session.get("metadata") if isinstance(session, dict) else getattr(session, "metadata", None) or {}
        return seed_intake_business_from_stripe_metadata(order_service, order, meta)
    except Exception as e:
        print(f"[enrich_order_intake_from_checkout_session] non-fatal: {e!r}")
        return order


def _order_business_keys(order: dict) -> set:
    """
    Return possible business keys for an order/subscription row.
    Includes upgraded_from_token key and intake.business_name key when available.
    """
    keys = set()
    if not isinstance(order, dict):
        return keys
    up = (order.get("upgraded_from_token") or "").strip()
    if up:
        keys.add(f"token:{up}")
    intake = order.get("intake") or {}
    if isinstance(intake, dict):
        biz = _normalize_business_key((intake.get("business_name") or "").strip())
        if biz:
            keys.add(f"biz:{biz}")
    # Forward-compatible: if a canonical key is later persisted directly on the row.
    persisted = _normalize_business_key((order.get("business_key") or "").strip())
    if persisted:
        keys.add(f"biz:{persisted}")
    return keys


def _target_business_key_from_request(copy_from: str, explicit_business_key: str, business_name_raw: str) -> str:
    """Build canonical business key for duplicate-subscription guard."""
    if copy_from:
        return f"token:{copy_from}"
    if explicit_business_key:
        bk = _normalize_business_key(explicit_business_key)
        return f"biz:{bk}" if bk else ""
    if business_name_raw:
        bk = _normalize_business_key(business_name_raw)
        return f"biz:{bk}" if bk else ""
    return ""


def _validate_launch_event_window(launch_desc: str, pack_start_date: str) -> Optional[str]:
    """
    Validate key-date text falls within the upcoming 30-day pack window.
    Returns an error message when a parseable date is outside the window; else None.
    """
    text = (launch_desc or "").strip()
    if not text:
        return None
    try:
        from datetime import datetime
        import re
        from services.caption_generator import _parse_key_date_from_text
    except Exception:
        return None
    start_raw = (pack_start_date or "").strip()
    if not start_raw:
        return None
    try:
        start = datetime.strptime(start_raw[:10], "%Y-%m-%d")
    except ValueError:
        return None

    month_names = (
        "january|february|march|april|may|june|july|august|september|october|november|december"
    )
    month_num = {m: i for i, m in enumerate(month_names.split("|"), 1)}
    t = text.lower()
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(" + month_names + r")(?:\s+(\d{4}))?", t)
    day_num = None
    month_idx = None
    year = start.year
    if m:
        day_num = int(m.group(1))
        month_idx = month_num.get(m.group(2))
        if m.group(3):
            year = int(m.group(3))
    if day_num is None or month_idx is None:
        m = re.search(r"(" + month_names + r")\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?", t)
        if m:
            month_idx = month_num.get(m.group(1))
            day_num = int(m.group(2))
            if m.group(3):
                year = int(m.group(3))
    if day_num is None or month_idx is None:
        return None
    try:
        event_date = datetime(year, month_idx, day_num)
    except ValueError:
        return "The date in 'What's happening this month?' is invalid. Please check it and try again."

    in_window_day = _parse_key_date_from_text(text, start_raw)
    if in_window_day is not None:
        return None
    return (
        f"The date '{event_date.strftime('%d %B %Y')}' is outside your next 30-day captions window "
        f"(starting {start.strftime('%d %B %Y')}). Please correct it so we can phase before/on/after content correctly."
    )


def _customer_has_blocking_captions_subscription(email: str, target_business_key: Optional[str] = None) -> bool:
    """
    True if this customer already has an active/trialing/past_due Captions subscription in Stripe.
    Each completed subscription checkout creates a new Stripe subscription + caption_orders row;
    this guard prevents accidental duplicate monthly subscriptions.
    If target_business_key is provided, only blocks when an existing active subscription
    matches that same business context (allows multiple businesses under one email).
    """
    if not email or "@" not in email:
        return False
    import stripe

    if not Config.STRIPE_SECRET_KEY:
        return False
    stripe.api_key = Config.STRIPE_SECRET_KEY
    from services.caption_order_service import CaptionOrderService

    co_svc = CaptionOrderService()
    orders = co_svc.get_by_customer_email_including_stripe_customer(email.strip().lower())
    target_business_key = (target_business_key or "").strip()
    seen_subs = set()
    for o in orders:
        sid = (o.get("stripe_subscription_id") or "").strip()
        if not sid or sid in seen_subs:
            continue
        seen_subs.add(sid)
        try:
            sub = stripe.Subscription.retrieve(sid)
        except Exception as e:
            print(f"[captions_checkout_subscription] Stripe retrieve failed for sub {sid[:14]}...: {e}")
            continue
        if _stripe_subscription_blocks_new_checkout(sub):
            if not target_business_key:
                return True
            existing_keys = _order_business_keys(o)
            if target_business_key in existing_keys:
                return True
    return False


@captions_bp.route("/referral-code-check", methods=["GET"])
def referral_code_check():
    """Public: whether a Lumo refer-a-friend code exists (for /captions Apply button)."""
    code = (request.args.get("code") or "").strip()
    if len(code) < 4:
        return jsonify({"valid": False})
    try:
        from services.customer_auth_service import CustomerAuthService

        if CustomerAuthService().get_by_referral_code(code):
            return jsonify({"valid": True})
    except Exception:
        pass
    return jsonify({"valid": False})


@captions_bp.route("/captions-checkout", methods=["GET"])
def captions_checkout():
    """
    Create a Stripe Checkout Session and redirect to it.
    Query: ?platforms=N (1–4), ?selected=..., ?stories=1, ?currency=gbp|usd|eur.
    Base price covers 1; extra platforms and Stories use add-on prices (or price_data for USD/EUR).
    After payment, Stripe redirects to /captions-thank-you?session_id=xxx.
    """
    import stripe
    currency = _parse_currency(request)
    base_price_id = _get_base_price_id(currency)
    if not Config.STRIPE_SECRET_KEY or not base_price_id:
        if Config.CAPTIONS_PAYMENT_LINK:
            return redirect(Config.CAPTIONS_PAYMENT_LINK)
        return jsonify({"error": "Checkout not configured (STRIPE_SECRET_KEY, STRIPE_CAPTIONS_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    platforms = _parse_platforms(request)
    selected = _parse_selected_platforms(request)
    if not selected and platforms == 1:
        selected = "Instagram & Facebook"
    stories = _parse_stories(request)
    checkout_email, email_error = _parse_checkout_email(request)
    if email_error:
        return redirect(f"{request.host_url.rstrip('/')}/captions?error=checkout_email_invalid#pricing", code=302)
    # Match subscription checkout: prefill Stripe email when logged in (one-off page has no email fields).
    if not checkout_email:
        from api.auth_routes import get_current_customer

        cust = get_current_customer()
        if cust and (cust.get("email") or "").strip():
            checkout_email = (cust.get("email") or "").strip().lower()
    extra_price_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID", None) or "").strip()
    stories_price_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_PRICE_ID", None) or "").strip()
    amounts = _CURRENCY_ADDON_AMOUNTS.get(currency, _CURRENCY_ADDON_AMOUNTS["gbp"])
    if platforms > 1 and not extra_price_id and currency == "gbp":
        return redirect(f"{request.host_url.rstrip('/')}/captions?error=extra_platform_not_configured", code=302)
    if platforms > 1 and currency != "gbp" and not amounts:
        return redirect(f"{request.host_url.rstrip('/')}/captions?error=extra_platform_not_configured", code=302)
    base = _base_url_for_redirect()
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
    line_items = [{"price": base_price_id, "quantity": 1}]
    if platforms > 1:
        addon_qty = platforms - 1
        label = f"+{addon_qty} platform" if addon_qty == 1 else f"+{addon_qty} platforms"
        if currency == "gbp" and extra_price_id:
            line_items.append({"price": extra_price_id, "quantity": addon_qty})
        else:
            line_items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": amounts["extra_oneoff"],
                    "product_data": {
                        "name": label,
                        "description": "Extra platform add-on for 30 Days Captions.",
                    },
                },
                "quantity": addon_qty,
            })
    if stories:
        if currency == "gbp" and stories_price_id:
            line_items.append({"price": stories_price_id, "quantity": 1})
        else:
            line_items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": amounts["stories_oneoff"],
                    "product_data": {
                        "name": "30 Days Story Ideas",
                        "description": "Story prompts for Instagram & Facebook. Add-on for 30 Days Captions.",
                    },
                },
                "quantity": 1,
            })
    business_name_raw = (request.args.get("business_name") or "").strip()
    explicit_business_key = (request.args.get("business_key") or "").strip()
    metadata = {"product": "captions", "platforms": str(platforms), "include_stories": "1" if stories else "0"}
    if selected:
        metadata["selected_platforms"] = selected
    normalized_business_name = _normalize_business_key(business_name_raw)
    if normalized_business_name and not explicit_business_key:
        metadata["business_key"] = normalized_business_name
    elif explicit_business_key:
        metadata["business_key"] = _normalize_business_key(explicit_business_key)
    if business_name_raw:
        metadata["business_name"] = business_name_raw[:120]
    create_params = {
        "mode": "payment",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata,
        "allow_promotion_codes": True,
    }
    if checkout_email:
        create_params["customer_email"] = checkout_email
    try:
        session = stripe.checkout.Session.create(**create_params)
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-correct-email", methods=["POST"])
def captions_correct_email():
    """
    Correct checkout email for a paid order and resend intake link.
    Body: {"session_id": "...", "email": "...", "email_confirm": "..."}
    """
    payload = request.get_json(silent=True) or {}
    session_id = (payload.get("session_id") or "").strip()
    recovery_token = (payload.get("recovery_token") or "").strip()
    new_email = (payload.get("email") or "").strip().lower()
    confirm_email = (payload.get("email_confirm") or "").strip().lower()
    if not session_id:
        return jsonify({"status": "error", "error": "Missing session_id."}), 400
    if not new_email or "@" not in new_email:
        return jsonify({"status": "error", "error": "Please enter a valid email."}), 400
    if new_email != confirm_email:
        return jsonify({"status": "error", "error": "Email addresses do not match."}), 400
    try:
        import stripe
        from services.caption_order_service import CaptionOrderService
    except Exception:
        return jsonify({"status": "error", "error": "Service unavailable."}), 503
    order_service = CaptionOrderService()
    order = order_service.get_by_stripe_session_id(session_id)
    if not order:
        return jsonify({"status": "error", "error": "Order not found yet. Please try again in a few seconds."}), 404
    order_id = str(order.get("id") or "").strip()
    if not order_id:
        return jsonify({"status": "error", "error": "Order not found."}), 404
    if not _verify_email_recovery_token(recovery_token, order_id, session_id):
        return jsonify({"status": "error", "error": "Email correction link expired. Please refresh this page and try again."}), 403
    client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    if not _email_change_allowed(order_id, client_ip):
        return jsonify({"status": "error", "error": "Too many attempts. Please try again later."}), 429
    if not _email_resend_allowed(order_id):
        return jsonify({"status": "error", "error": "Please wait a few minutes before requesting another resend."}), 429
    try:
        if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
            return jsonify({"status": "error", "error": "Stripe is not configured."}), 503
        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
        session = stripe.checkout.Session.retrieve(session_id)
        payment_status = (_get_session_attr(session, "payment_status") or "").strip().lower()
        if payment_status not in ("paid", "no_payment_required"):
            return jsonify({"status": "error", "error": "Checkout is not completed yet."}), 400
    except Exception as e:
        print(f"[captions-correct-email] Stripe session verify failed: {e!r}")
        return jsonify({"status": "error", "error": "Unable to verify checkout session."}), 400
    try:
        old_email = (order.get("customer_email") or "").strip().lower()
        ok = order_service.update(order_id, {"customer_email": new_email})
        if not ok:
            return jsonify({"status": "error", "error": "Unable to update email."}), 500
        try:
            order_service.remove_from_deleted_blocklist(new_email)
        except Exception:
            pass
        updated = order_service.get_by_id(order_id) or order
        _append_email_change_event(
            order_service,
            updated,
            old_email=old_email,
            new_email=new_email,
            ip=client_ip,
            user_agent=(request.headers.get("User-Agent") or ""),
        )
        updated = order_service.get_by_id(order_id) or updated
        _send_intake_email_for_order(updated, skip_checkout_confirmation_dedupe=True)
        intake_url = _build_intake_url(updated)
        is_sub = bool((updated.get("stripe_subscription_id") or "").strip())
        is_pref = bool((updated.get("upgraded_from_token") or "").strip())
        subscription_first_pack_immediate = (
            is_sub
            and is_pref
            and _stripe_checkout_get_pack_now(session_id)
        )
        return jsonify({
            "status": "ok",
            "customer_email": new_email,
            "intake_url": intake_url,
            "email_recovery_token": _make_email_recovery_token(order_id, session_id),
            "is_subscription": is_sub,
            "is_prefilled_from_oneoff": is_pref,
            "subscription_first_pack_immediate": subscription_first_pack_immediate,
        }), 200
    except Exception as e:
        print(f"[captions-correct-email] Failed to update/resend: {e!r}")
        return jsonify({"status": "error", "error": "Could not update email right now. Please try again."}), 500


@captions_bp.route("/captions-checkout-subscription", methods=["GET"])
def captions_checkout_subscription():
    """
    Create a Stripe Checkout Session for Captions subscription.
    Query: ?platforms=N (1–4), ?selected=..., ?stories=1, ?currency=gbp|usd|eur, ?get_pack_now=1 (upgrade only).
    When get_pack_now=1 and copy_from=TOKEN: one-time payment for first month + immediate pack; subscription created with trial so next pack in 30 days.
    """
    from api.auth_routes import get_current_customer
    copy_from = (request.args.get("copy_from") or "").strip()
    business_name_raw = (request.args.get("business_name") or "").strip()
    explicit_business_key = (request.args.get("business_key") or "").strip()
    get_pack_now = request.args.get("get_pack_now", "").strip().lower() in ("1", "true", "yes", "on")
    one_off = None
    customer = get_current_customer()
    if not customer:
        from urllib.parse import quote
        next_url = request.url
        signup_url = url_for("customer_signup_page") + "?next=" + quote(next_url, safe="")
        return redirect(signup_url)
    import stripe
    currency = _parse_currency(request)
    price_id = _get_sub_price_id(currency)
    if not Config.STRIPE_SECRET_KEY or not price_id:
        return jsonify({"error": "Subscription not configured (STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    target_business_key = _target_business_key_from_request(copy_from, explicit_business_key, business_name_raw)
    # Prevent multiple active Captions subscriptions for the same account (each checkout = new Stripe sub + new order row).
    if target_business_key and customer and (customer.get("email") or "").strip():
        try:
            if _customer_has_blocking_captions_subscription(
                (customer.get("email") or "").strip().lower(),
                target_business_key=target_business_key,
            ):
                return redirect(url_for("account_page") + "?subscription_duplicate=1")
        except Exception as e:
            print(f"[captions_checkout_subscription] duplicate guard failed (non-fatal): {e}")
    platforms = _parse_platforms(request)
    selected = _parse_selected_platforms(request)
    if not selected and platforms == 1:
        selected = "Instagram & Facebook"
    stories = _parse_stories(request)
    reminders_on = request.args.get("form_reminders", "1").strip().lower() not in ("0", "false", "no", "off")
    base = _base_url_for_redirect()
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
    metadata = {"product": "captions_subscription", "platforms": str(platforms), "include_stories": "1" if stories else "0"}
    metadata["reminder_opt_out"] = "0" if reminders_on else "1"
    if selected:
        metadata["selected_platforms"] = selected
    if target_business_key.startswith("biz:"):
        metadata["business_key"] = target_business_key[len("biz:"):]
    if copy_from:
        metadata["copy_from"] = copy_from
        try:
            from services.caption_order_service import CaptionOrderService
            one_off = CaptionOrderService().get_by_token(copy_from)
        except Exception:
            one_off = None
        if not one_off:
            return jsonify({"error": "Base one-off order not found for this upgrade."}), 400
        one_off_email = (one_off.get("customer_email") or "").strip().lower()
        customer_email = (customer.get("email") or "").strip().lower()
        if not one_off_email or not customer_email or one_off_email != customer_email:
            return jsonify({"error": "You can only upgrade your own one-off order."}), 403
        # Upgrade URLs omit business_name; copy from the one-off intake so Stripe metadata
        # and webhook emails (subject, receipt, welcome) include the business name.
        if not (business_name_raw or "").strip():
            io = one_off.get("intake") if isinstance(one_off.get("intake"), dict) else {}
            bn = (io.get("business_name") or "").strip()
            if bn:
                business_name_raw = bn
    normalized_business_name = _normalize_business_key(business_name_raw)
    if normalized_business_name and not metadata.get("business_key"):
        metadata["business_key"] = normalized_business_name
    if (business_name_raw or "").strip():
        metadata["business_name"] = business_name_raw[:120]
    if get_pack_now:
        # Safety guard: only allow immediate first subscription pack after the base one-off
        # has already been delivered, so customers are never charged twice for the same day.
        if not copy_from:
            return jsonify({"error": "Get pack now is only available for upgrades from a one-off order."}), 400
        if not (one_off and (one_off.get("status") == "delivered" or one_off.get("delivered_at"))):
            return jsonify({
                "error": "Your one-off pack hasn't been delivered yet. Leave this unchecked and your subscription will start 30 days after delivery."
            }), 400
        metadata["get_pack_now"] = "1"

    # Upgraders (copy_from) without get_pack_now: first charge on first pack date (billing_cycle_anchor), no “X days free” trial wording
    subscription_data = None
    if copy_from and not get_pack_now:
        from datetime import datetime, timedelta, timezone
        try:
            if one_off:
                delivered_at_raw = one_off.get("delivered_at") or one_off.get("updated_at") or one_off.get("created_at")
                if delivered_at_raw:
                    if isinstance(delivered_at_raw, str):
                        dt = datetime.fromisoformat(delivered_at_raw.replace("Z", "+00:00"))
                    else:
                        dt = delivered_at_raw
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    anchor_dt = dt + timedelta(days=30)
                    subscription_data = {
                        "billing_cycle_anchor": int(anchor_dt.timestamp()),
                        "proration_behavior": "none",
                    }
        except Exception as e:
            print(f"[captions_checkout_subscription] billing_cycle_anchor from one-off failed: {e}")
        if not subscription_data:
            # Fallback: first charge 30 days from now
            anchor_dt = datetime.now(timezone.utc) + timedelta(days=30)
            subscription_data = {
                "billing_cycle_anchor": int(anchor_dt.timestamp()),
                "proration_behavior": "none",
            }

    extra_sub_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    stories_sub_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    amounts = _CURRENCY_ADDON_AMOUNTS.get(currency, _CURRENCY_ADDON_AMOUNTS["gbp"])
    if platforms > 1 and currency == "gbp" and not extra_sub_id:
        return redirect(f"{request.host_url.rstrip('/')}/captions?error=extra_platform_not_configured", code=302)
    line_items = [{"price": price_id, "quantity": 1}]
    if platforms > 1:
        addon_qty = platforms - 1
        label = f"+{addon_qty} platform" if addon_qty == 1 else f"+{addon_qty} platforms"
        if currency == "gbp" and extra_sub_id:
            line_items.append({"price": extra_sub_id, "quantity": addon_qty})
        else:
            line_items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": amounts["extra_sub"],
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": label,
                        "description": "Extra platform add-on for 30 Days Captions. Billed monthly.",
                    },
                },
                "quantity": addon_qty,
            })
    if stories:
        if currency == "gbp" and stories_sub_id:
            line_items.append({"price": stories_sub_id, "quantity": 1})
        else:
            line_items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": amounts["stories_sub"],
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": "30 Days Story Ideas",
                        "description": "Story prompts add-on. Billed monthly.",
                    },
                },
                "quantity": 1,
            })
    create_params = {
        "mode": "subscription",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata,
        "allow_promotion_codes": True,
    }
    if subscription_data:
        create_params["subscription_data"] = subscription_data
        # Clear charge-date wording near submit button (no “days free” with billing_cycle_anchor)
        anchor_ts = subscription_data.get("billing_cycle_anchor")
        if anchor_ts:
            from datetime import datetime, timezone
            try:
                first_charge_dt = datetime.fromtimestamp(anchor_ts, tz=timezone.utc)
                first_charge_str = first_charge_dt.strftime("%d %B %Y")
                prices = _DISPLAY_PRICES.get(currency, _DISPLAY_PRICES["gbp"])
                total = prices["sub"] + (platforms - 1) * prices["extra_sub"] + (prices["stories_sub"] if stories else 0)
                symbol = prices["symbol"]
                create_params["custom_text"] = {
                    "submit": {
                        "message": f"You will be charged {symbol}{total} every 30 days starting on {first_charge_str}."
                    }
                }
            except Exception as e:
                print(f"[captions_checkout_subscription] custom_text for billing anchor: {e}")
    if customer and (customer.get("email") or "").strip():
        create_params["customer_email"] = (customer.get("email") or "").strip()
    try:
        session = stripe.checkout.Session.create(**create_params)
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-setup-check", methods=["GET"])
def captions_setup_check():
    """
    Check if captions checkout and multi-platform are correctly configured.
    Returns JSON: checkout_configured, multi_platform_oneoff, multi_platform_sub, stories_addon_available.
    Use to verify Railway env vars: visit /api/captions-setup-check
    """
    checkout_ok = bool(Config.STRIPE_SECRET_KEY and Config.STRIPE_CAPTIONS_PRICE_ID)
    extra_oneoff = bool((getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID", None) or "").strip())
    sub_price = bool((getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip())
    extra_sub = bool((getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip())
    stories_oneoff = bool((getattr(Config, "STRIPE_CAPTIONS_STORIES_PRICE_ID", None) or "").strip())
    stories_sub = bool((getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip())
    return jsonify({
        "checkout_configured": checkout_ok,
        "multi_platform_oneoff": checkout_ok and extra_oneoff,
        "subscription_available": bool(Config.STRIPE_SECRET_KEY and sub_price),
        "multi_platform_sub": bool(Config.STRIPE_SECRET_KEY and sub_price and extra_sub),
        "stories_addon_available": stories_oneoff and stories_sub,
    })


@captions_bp.route("/captions-webhook-test", methods=["GET"])
def captions_webhook_test():
    """
    Run the same steps as the Stripe webhook handler (create order + send intake email).
    Open in browser to see the REAL error on Railway: https://lumo-22-production.up.railway.app/api/captions-webhook-test
    Returns JSON: {"ok": true} or {"ok": false, "error": "the actual error message"}.
    Disabled in production — unauthenticated GET could create real orders and send real email (spam / abuse).
    """
    if Config.is_production():
        return jsonify({"ok": False, "error": "Not available."}), 404
    test_email = request.args.get("email", "test@example.com").strip() or "test@example.com"
    session = {
        "id": "cs_test_diagnostic",
        "customer_details": {"email": test_email},
        "metadata": {"product": "captions"},
    }
    try:
        from services.caption_order_service import CaptionOrderService
        from services.notifications import NotificationService

        order_service = CaptionOrderService()
        order = order_service.create_order(
            customer_email=test_email,
            stripe_session_id=session.get("id"),
        )
        token = order["token"]
        intake_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={token}"
        subject = "Your 30 Days of Social Media Captions - next step"
        body = f"""Hi,

Thanks for your order. Please complete this form: {intake_url}

Lumo 22
"""
        notif = NotificationService()
        ok = notif.send_email(test_email, subject, body)
        if ok:
            return jsonify({"ok": True, "message": "Order created and email sent. Webhook would succeed."}), 200
        return jsonify({"ok": False, "error": "SendGrid returned False (email not sent)"}), 200
    except Exception as e:
        err = (str(e) or repr(e))[:500]
        err = "".join(c for c in err if ord(c) < 128)
        return jsonify({"ok": False, "error": err or "Unknown error"}), 200


def _get_customer_email_from_stripe_session(session) -> str:
    """Get customer email from Stripe Checkout Session (customer_details.email). Works with dict or StripeObject."""
    details = session.get("customer_details") if isinstance(session, dict) else getattr(session, "customer_details", None)
    if details is not None:
        email = details.get("email") if isinstance(details, dict) else getattr(details, "email", None)
        if email and isinstance(email, str):
            return email.strip()
    email = session.get("customer_email") if isinstance(session, dict) else getattr(session, "customer_email", None)
    return email.strip() if email and isinstance(email, str) else ""


def _get_session_attr(session, key, default=None):
    """Get attribute from Stripe session (dict or StripeObject)."""
    if isinstance(session, dict):
        return session.get(key, default)
    return getattr(session, key, default)


def _stripe_checkout_get_pack_now(session_id: Optional[str]) -> bool:
    """
    True when Checkout Session metadata has get_pack_now (upgrade: charge today + first subscription pack generated now).
    Used on thank-you page so copy can confirm the first pack is on the way vs deferred billing.
    """
    if not session_id or not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
        return False
    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
        session = stripe.checkout.Session.retrieve(session_id)
        meta = _get_session_attr(session, "metadata") or {}
        v = meta.get("get_pack_now", "") if hasattr(meta, "get") else getattr(meta, "get_pack_now", "") or ""
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _build_intake_url(order: dict) -> str:
    """Build intake URL for an order, including copy_from when order was upgraded from one-off."""
    token = (order.get("token") or "").strip()
    if not token:
        return ""
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://lumo-22-production.up.railway.app"
    intake_url = f"{base}/captions-intake?t={token}"
    copy_from = (order.get("upgraded_from_token") or "").strip()
    if copy_from:
        intake_url += f"&copy_from={copy_from}"
    return intake_url


def _send_intake_email_for_order(
    order: dict,
    *,
    skip_checkout_confirmation_dedupe: bool = False,
    checkout_session: Optional[Any] = None,
) -> bool:
    """Send combined order confirmation + intake email, or subscription-welcome for upgrade-from-one-off (API fallback).
    When skip_checkout_confirmation_dedupe is False, claims checkout_confirmation_email_sent_at first (cross-worker dedupe).
    When True, caller already claimed (e.g. Stripe webhook); still releases claim if send fails."""
    customer_email = (order.get("customer_email") or "").strip()
    if not customer_email or "@" not in customer_email:
        return False
    intake_url = _build_intake_url(order)
    if not intake_url:
        return False
    upgraded_from_oneoff = bool((order.get("upgraded_from_token") or "").strip())
    oid = str(order.get("id") or "").strip()
    order_svc = None
    if not skip_checkout_confirmation_dedupe and oid:
        from services.caption_order_service import CaptionOrderService

        order_svc = CaptionOrderService()
        if not order_svc.try_claim_checkout_confirmation_email(oid):
            print(f"[captions-intake-link] Skip duplicate checkout confirmation email for order {oid[:8]}...")
            return False
    elif skip_checkout_confirmation_dedupe and oid:
        from services.caption_order_service import CaptionOrderService

        order_svc = CaptionOrderService()
    ok = False
    try:
        from services.notifications import NotificationService

        notif = NotificationService()
        if upgraded_from_oneoff:
            # Upgrade-from-one-off: prefilled form already exists, so we must not send the standard receipt copy
            # that says "complete your short intake form".
            ok = notif.send_subscription_welcome_prefilled_email(customer_email, intake_url, order=order)
            if ok:
                print(f"[captions-intake-link] Sent subscription welcome (prefilled) email to {customer_email}")
            else:
                print(f"[captions-intake-link] Subscription welcome email NOT sent to {customer_email}")
        else:
            stripe_session = checkout_session
            if stripe_session is None:
                sid = (order.get("stripe_session_id") or "").strip()
                if sid and (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
                    try:
                        import stripe
                        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
                        stripe_session = stripe.checkout.Session.retrieve(sid)
                    except Exception:
                        stripe_session = None
            ok = notif.send_intake_link_email(customer_email, intake_url, order, session=stripe_session)
            if ok:
                print(f"[captions-intake-link] Sent intake email to {customer_email}")
            else:
                print(f"[captions-intake-link] Intake email NOT sent (send_email returned False) to {customer_email}")
        if not ok and oid and order_svc:
            order_svc.release_checkout_confirmation_email_claim(oid)
        return ok
    except Exception as e:
        if oid and order_svc:
            order_svc.release_checkout_confirmation_email_claim(oid)
        print(f"[captions-intake-link] Failed to send email: {e!r}")
        return False


@captions_bp.route("/captions-intake-link", methods=["GET"])
def captions_intake_link():
    """
    Return the intake form URL for a Stripe checkout session (for thank-you page redirect).
    Thank-you page polls this until the order exists. If the webhook hasn't run yet, we create the order
    from the Stripe session here so the user isn't stuck.
    """
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
    except Exception:
        return jsonify({"error": "Service unavailable"}), 503
    order = order_service.get_by_stripe_session_id(session_id)
    if order:
        print(f"[captions-intake-link] Order found for session_id={session_id[:20]}...")
    if not order:
        # Get checkout email from Stripe and try to find order by email first (no user input needed)
        print(f"[captions-intake-link] No order for session_id={session_id[:20] if session_id else ''}..., trying Stripe then lookup by email")
        try:
            import stripe
            if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
                return jsonify({"status": "pending"}), 200
            stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
            session = stripe.checkout.Session.retrieve(session_id, expand=["customer_details"])
            if not session:
                return jsonify({"status": "pending"}), 200
            customer_email = _get_customer_email_from_stripe_session(session)
            if customer_email and "@" in customer_email:
                # Find order by checkout email (prefer one still awaiting intake) so user goes straight to buttons
                orders = order_service.get_by_customer_email(customer_email)
                for o in orders or []:
                    if not (o.get("token") or "").strip():
                        continue
                    if (o.get("status") or "").strip().lower() == "awaiting_intake":
                        order = o
                        print(f"[captions-intake-link] Order found by checkout email (awaiting_intake)")
                        break
                if not order:
                    for o in orders or []:
                        if (o.get("token") or "").strip():
                            order = o
                            print(f"[captions-intake-link] Order found by checkout email (most recent)")
                            break
            if not order and (not customer_email or "@" not in customer_email):
                return jsonify({"status": "pending"}), 200
            if not order:
                # Create order from session so thank-you page isn't stuck
                meta = _get_session_attr(session, "metadata") or {}
                if hasattr(meta, "get"):
                    platforms_count = meta.get("platforms")
                    selected_platforms = (meta.get("selected_platforms") or "").strip() or None
                    include_stories = str(meta.get("include_stories") or "").lower() in ("1", "true", "yes")
                    copy_from = (meta.get("copy_from") or "").strip() or None
                else:
                    platforms_count = getattr(meta, "platforms", None)
                    selected_platforms = (getattr(meta, "selected_platforms", None) or "").strip() or None
                    include_stories = str(getattr(meta, "include_stories", "") or "").lower() in ("1", "true", "yes")
                    copy_from = (getattr(meta, "copy_from", None) or "").strip() or None
                try:
                    platforms_count = max(1, int(platforms_count)) if platforms_count is not None else 1
                except (TypeError, ValueError):
                    platforms_count = 1
                currency = _get_session_attr(session, "currency") or "gbp"
                if isinstance(currency, str):
                    currency = currency.strip().lower()
                else:
                    currency = "gbp"
                if currency not in ("gbp", "usd", "eur"):
                    currency = "gbp"
                stripe_customer_id = (_get_session_attr(session, "customer") or "").strip() or None
                stripe_subscription_id = (_get_session_attr(session, "subscription") or "").strip() or None
                upgraded_from = copy_from if stripe_subscription_id else None
                order = order_service.create_order(
                    customer_email=customer_email,
                    stripe_session_id=session_id,
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                    platforms_count=platforms_count,
                    selected_platforms=selected_platforms,
                    include_stories=include_stories,
                    currency=currency,
                    upgraded_from_token=upgraded_from,
                )
                # Persist business context early (before full intake) so emails and duplicate guard have stable keys.
                order = seed_intake_business_from_stripe_metadata(order_service, order, meta)
                print(f"[captions-intake-link] Created order from Stripe session session_id={session_id[:20]}...")
                # Send intake email so customer gets it even if webhook never runs
                _send_intake_email_for_order(order)
        except Exception as e:
            print(f"[captions-intake-link] Fallback create failed session_id={session_id[:20] if session_id else ''}... error={e!r}")
            if getattr(e, "code", None) == "resource_missing" or "No such checkout.session" in str(e):
                return jsonify({"status": "pending"}), 200
            # Race: webhook may have created the order; try to use it
            order = order_service.get_by_stripe_session_id(session_id)
            if not order:
                # Don't 500: return pending so thank-you page can keep polling or show fallback
                return jsonify({"status": "pending"}), 200
    if not order:
        return jsonify({"status": "pending"}), 200
    intake_url = _build_intake_url(order)
    if not intake_url:
        return jsonify({"status": "pending"}), 200
    customer_email = (order.get("customer_email") or "").strip()
    # Only send intake email when WE created the order (fallback); if order existed, webhook already sent
    is_subscription = bool((order.get("stripe_subscription_id") or "").strip())
    is_prefilled_from_oneoff = bool((order.get("upgraded_from_token") or "").strip())
    subscription_first_pack_immediate = (
        is_subscription
        and is_prefilled_from_oneoff
        and _stripe_checkout_get_pack_now(session_id)
    )
    print(f"[captions-intake-link] Returning intake_url for session_id={session_id[:20]}...")
    return jsonify({
        "status": "ok",
        "intake_url": intake_url,
        "customer_email": customer_email or None,
        "email_recovery_token": _make_email_recovery_token(str(order.get("id")), session_id),
        "is_subscription": is_subscription,
        "is_prefilled_from_oneoff": is_prefilled_from_oneoff,
        "subscription_first_pack_immediate": subscription_first_pack_immediate,
    }), 200


@captions_bp.route("/captions-intake-link-by-email", methods=["GET"])
def captions_intake_link_by_email():
    """
    Return the intake form URL for the most recent caption order with this email.
    Used when thank-you page has no session_id or session lookup fails.
    Requires login; requested email must match logged-in customer (prevents token disclosure by email enumeration).
    """
    from api.auth_routes import get_current_customer
    customer = get_current_customer()
    if not customer:
        return jsonify({"status": "error", "error": "Please log in to get your form link, or check your email for the link we sent."}), 401
    customer_email = (customer.get("email") or "").strip().lower()
    if not customer_email or "@" not in customer_email:
        return jsonify({"status": "error", "error": "Invalid account"}), 400

    email = (request.args.get("email") or request.args.get("e") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"status": "error", "error": "Valid email required"}), 400
    if email != customer_email:
        return jsonify({"status": "error", "error": "This email does not match your account."}), 403
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
    except Exception:
        return jsonify({"error": "Service unavailable"}), 503
    orders = order_service.get_by_customer_email(email)
    order = None
    # Prefer an order still awaiting intake (new payment) so they get an empty form, not an old prefilled one
    for o in orders or []:
        if not (o.get("token") or "").strip():
            continue
        if (o.get("status") or "").strip().lower() == "awaiting_intake":
            order = o
            break
    if not order:
        for o in orders or []:
            if (o.get("token") or "").strip():
                order = o
                break
    if not order:
        return jsonify({"status": "error", "error": "No order found for this email. Check the address or contact us."}), 200
    intake_url = _build_intake_url(order)
    if not intake_url:
        return jsonify({"status": "error", "error": "Order has no token."}), 200
    # If checkout email was never sent (e.g. webhook missed), try atomic claim + send once.
    # Do not use skip_checkout_confirmation_dedupe here — that bypassed DB dedupe and duplicated
    # the webhook confirmation when users hit "Get form link" after checkout.
    if (order.get("status") or "").strip().lower() == "awaiting_intake" and order.get("id"):
        _send_intake_email_for_order(order)
    is_subscription = bool((order.get("stripe_subscription_id") or "").strip())
    is_prefilled_from_oneoff = bool((order.get("upgraded_from_token") or "").strip())
    sid = (order.get("stripe_session_id") or "").strip()
    subscription_first_pack_immediate = (
        bool(sid)
        and is_subscription
        and is_prefilled_from_oneoff
        and _stripe_checkout_get_pack_now(sid)
    )
    return jsonify({
        "status": "ok",
        "intake_url": intake_url,
        "customer_email": email,
        "is_subscription": is_subscription,
        "is_prefilled_from_oneoff": is_prefilled_from_oneoff,
        "subscription_first_pack_immediate": subscription_first_pack_immediate,
    }), 200


_SUB_PACK_DELIVERY_DEDUPE: dict[str, float] = {}
_SUB_PACK_DELIVERY_DEDUPE_LOCK = threading.Lock()
_SUB_PACK_DELIVERY_DEDUPE_TTL_SEC = 180.0


def _subscription_pack_delivery_recent_duplicate(order_id: str) -> bool:
    """Suppress a second subscription renewal / get-pack-sooner run within TTL (webhook + API race)."""
    now = time.monotonic()
    with _SUB_PACK_DELIVERY_DEDUPE_LOCK:
        stale = [
            k
            for k, ts in _SUB_PACK_DELIVERY_DEDUPE.items()
            if (now - ts) > _SUB_PACK_DELIVERY_DEDUPE_TTL_SEC * 2
        ]
        for k in stale:
            _SUB_PACK_DELIVERY_DEDUPE.pop(k, None)
        ts = _SUB_PACK_DELIVERY_DEDUPE.get(order_id)
        return ts is not None and (now - ts) < _SUB_PACK_DELIVERY_DEDUPE_TTL_SEC


def _subscription_pack_delivery_register(order_id: str) -> None:
    with _SUB_PACK_DELIVERY_DEDUPE_LOCK:
        _SUB_PACK_DELIVERY_DEDUPE[order_id] = time.monotonic()


def _run_generation_and_deliver(
    order_id: str,
    *,
    force_redeliver: bool = False,
    force_captions_only: bool = False,
):
    """Background: generate captions, save, email client. Runs outside request context.
    force_redeliver: when True, regenerate and email even if status is 'delivered', and retry even if
    status is 'generating' (support redeliver). Otherwise stale generating (>25m) still retries like recovery cron.
    force_captions_only: when True, skip stories generation and deliver captions only."""
    import traceback
    from datetime import datetime
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator, extract_day_categories_from_captions_md
    from services.notifications import NotificationService, _captions_delivery_email_html

    print(f"[Captions] Starting generation for order {order_id} (force_redeliver={force_redeliver})")
    order_service = CaptionOrderService()
    row = order_service.get_by_id(order_id)
    if not row:
        print(f"[Captions] Order {order_id} not found, skipping")
        return (False, "Order not found")
    status = (row.get("status") or "").strip()
    if status == "delivered" and not force_redeliver:
        print(f"[Captions] Order {order_id} already delivered, skipping duplicate")
        return (True, None)
    if status == "generating":
        # In-flight run: skip. Stuck "generating" (worker died): allow retry after 25m (same rule as
        # row_needs_first_delivery_retry). Support/cron redeliver uses force_redeliver to bypass.
        allow_retry = force_redeliver
        if not allow_retry:
            from datetime import timedelta, timezone

            updated = row.get("updated_at") or row.get("created_at")
            if updated:
                try:
                    now = datetime.now(timezone.utc)
                    if isinstance(updated, str):
                        udt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    else:
                        udt = updated
                    if udt.tzinfo is None:
                        udt = udt.replace(tzinfo=timezone.utc)
                    allow_retry = udt < now - timedelta(minutes=25)
                except Exception:
                    allow_retry = True
            else:
                allow_retry = True
        if not allow_retry:
            print(f"[Captions] Order {order_id} already generating, skipping duplicate")
            return (True, None)
        if force_redeliver:
            print(f"[Captions] Order {order_id} force redeliver: retrying despite generating status")
        else:
            print(f"[Captions] Order {order_id} stale generating (>25m); retrying delivery")
    intake = row.get("intake") or {}
    token = (row.get("token") or "").strip()
    customer_email = (row.get("customer_email") or "").strip()
    if not customer_email:
        print(f"[Captions] No customer_email for order {order_id}, skipping")
        try:
            order_service.record_delivery_failure(order_id, "No customer_email for order")
        except Exception as rec_err:
            print(f"[Captions] record_delivery_failure failed: {rec_err}")
        order_service.set_failed(order_id)
        return (False, "No customer_email for order")

    if force_redeliver and (row.get("stripe_subscription_id") or "").strip():
        if _subscription_pack_delivery_recent_duplicate(str(order_id)):
            print(f"[Captions] Order {order_id} subscription delivery dedupe: skipped rapid duplicate")
            return (True, None)

    # For subscriptions, pass previous pack themes so this month varies (avoid repetition)
    previous_pack_themes = None
    if row.get("stripe_subscription_id"):
        history = row.get("pack_history") or []
        if isinstance(history, list) and len(history) > 0:
            previous_pack_themes = [entry.get("day_categories") for entry in history if entry.get("day_categories")]
            if previous_pack_themes:
                print(f"[Captions] Subscription order {order_id}: varying from {len(previous_pack_themes)} previous pack(s)")

    order_service.set_generating(order_id)
    try:
        pack_start_date = datetime.utcnow().strftime("%Y-%m-%d")
        gen = CaptionGenerator()
        print(f"[Captions] Calling AI (provider={Config.AI_PROVIDER}) for order {order_id} (Day 1 = {pack_start_date})")
        stories_generation_failed = False
        stories_generation_status = "ok"
        if force_captions_only and intake.get("include_stories"):
            stories_generation_status = "skipped"
        try:
            if force_captions_only and intake.get("include_stories"):
                intake_no_stories = dict(intake or {})
                intake_no_stories["include_stories"] = False
                intake_no_stories["align_stories_to_captions"] = False
                captions_md = gen.generate(
                    intake_no_stories,
                    previous_pack_themes=previous_pack_themes,
                    pack_start_date=pack_start_date,
                )
            else:
                captions_md = gen.generate(intake, previous_pack_themes=previous_pack_themes, pack_start_date=pack_start_date)
        except RuntimeError as e:
            msg = str(e)
            if intake.get("include_stories") and "Stories output invalid after retry" in msg:
                # Do not block full delivery when Story Ideas generation fails repeatedly.
                # Fallback to captions-only so the customer still receives their core pack.
                print(f"[Captions] Stories generation failed for order {order_id}; retrying captions-only fallback: {msg}")
                intake_no_stories = dict(intake or {})
                intake_no_stories["include_stories"] = False
                intake_no_stories["align_stories_to_captions"] = False
                captions_md = gen.generate(
                    intake_no_stories,
                    previous_pack_themes=previous_pack_themes,
                    pack_start_date=pack_start_date,
                )
                stories_generation_failed = True
                stories_generation_status = "failed"
            else:
                raise
        from services.caption_pdf import build_caption_pdf, build_stories_pdf, get_logo_path
        logo_path = get_logo_path()
        try:
            pdf_bytes = build_caption_pdf(captions_md, logo_path=logo_path, pack_start_date=pack_start_date)
            filename = "30_Days_Captions.pdf"
            mime_type = "application/pdf"
            file_content_bytes = pdf_bytes
            file_content = None
        except Exception as e:
            print(f"[Captions] PDF build failed for order {order_id}, falling back to .md: {e}")
            filename = "30_Days_Captions.md"
            mime_type = "text/markdown"
            file_content_bytes = None
            file_content = captions_md
        extra_attachments = []
        if intake.get("include_stories"):
            stories_pdf = build_stories_pdf(
                captions_md, logo_path=logo_path, pack_start_date=pack_start_date
            )
            if stories_pdf:
                extra_attachments.append({
                    "filename": "30_Days_Story_Ideas.pdf",
                    "content": stories_pdf,
                    "mime_type": "application/pdf",
                })
        business_name = (intake.get("business_name") or "").strip()
        subject = "Your 30 Days of Social Media Captions"
        if business_name:
            subject = f"{subject} — {business_name}"
        has_sub = bool(row.get("stripe_subscription_id"))
        next_billing_plain = ""
        next_billing_display = None
        if force_redeliver and has_sub:
            try:
                import stripe

                stripe.api_key = Config.STRIPE_SECRET_KEY
                sub_nb = stripe.Subscription.retrieve((row.get("stripe_subscription_id") or "").strip())
                st = str(sub_nb.get("status") or "").strip().lower()
                if st != "canceled" or sub_nb.get("cancel_at_period_end"):
                    cpe = sub_nb.get("current_period_end")
                    if cpe is not None:
                        dt_nb = datetime.utcfromtimestamp(int(cpe))
                        next_billing_display = dt_nb.strftime("%d %B %Y")
                        next_billing_plain = f"Your next billing date is {next_billing_display}.\n\n"
            except Exception:
                pass
        base = (Config.BASE_URL or "").strip().rstrip("/")
        if not base.startswith("http"):
            base = "https://www.lumo22.com"
        if token:
            # Public backup links are signed and time-limited for non-account users.
            backup_captions_url = _build_public_download_url(base, token, "captions")
            backup_stories_url = _build_public_download_url(base, token, "stories") if extra_attachments else None
        else:
            backup_captions_url = f"{base}/account"
            backup_stories_url = None
        if extra_attachments:
            body = (
                "Hi,\n\n"
                + next_billing_plain
                + "Your 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. "
                "Both documents are attached.\n\nCopy each caption and story idea as you need them, or edit to fit.\n\n"
            )
        else:
            body = (
                "Hi,\n\n"
                + next_billing_plain
                + "Your 30 Days of Social Media Captions are ready. The document is attached.\n\n"
                "Copy each caption as you need it, or edit to fit.\n\n"
            )
            if stories_generation_failed:
                body += (
                    "Note: your Story Ideas add-on was not generated successfully in this run. "
                    "We've delivered your captions now so you can start posting.\n\n"
                )
        if has_sub:
            body += "Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account → Manage subscription.\n\n"
        body += "If attachments don't appear in your inbox, use your backup download link(s):\n"
        body += f"For your security, these backup links expire within {_public_download_expiry_hours()} hour(s).\n"
        body += backup_captions_url + "\n"
        if backup_stories_url:
            body += backup_stories_url + "\n"
        body += "\n"
        body += "Lumo 22\n"
        notif = NotificationService()
        delivery_html = _captions_delivery_email_html(
            bool(extra_attachments),
            has_subscription=has_sub,
            backup_captions_url=backup_captions_url,
            backup_stories_url=(backup_stories_url or ""),
            backup_link_expiry_hours=_public_download_expiry_hours(),
            business_name=business_name or None,
            next_billing_display=next_billing_display,
        )
        # Save generated artifacts first so customer can still download even if email send fails.
        stories_pdf_bytes = extra_attachments[0]["content"] if extra_attachments else None
        order_service.set_delivered(
            order_id,
            captions_md,
            stories_pdf_bytes=stories_pdf_bytes,
            captions_pdf_bytes=file_content_bytes if mime_type == "application/pdf" else None,
        )
        order_service.update(
            order_id,
            {
                "stories_generation_status": (
                    "failed" if stories_generation_failed else stories_generation_status
                )
            },
        )
        print(f"[Captions] Sending delivery email to {customer_email} for order {order_id}")
        ok, send_error = notif.send_email_with_attachment(
            customer_email,
            subject,
            body,
            filename=filename,
            file_content=file_content,
            file_content_bytes=file_content_bytes,
            mime_type=mime_type,
            extra_attachments=extra_attachments if extra_attachments else None,
            html_content=delivery_html,
        )
        if not ok:
            print(f"[Captions] Delivery email FAILED for order {order_id} to {customer_email}: {send_error}")
            return (True, send_error or "Delivery email not sent; backup links are available")
        if force_redeliver and has_sub:
            _subscription_pack_delivery_register(str(order_id))
        # For subscriptions, record this pack's day categories so next month can vary
        if row.get("stripe_subscription_id"):
            day_categories = extract_day_categories_from_captions_md(captions_md)
            if day_categories and any(day_categories):
                month_str = datetime.utcnow().strftime("%Y-%m")
                order_service.append_pack_history(order_id, month_str, day_categories)
        print(f"[Captions] Delivery email sent for order {order_id} to {customer_email}")
        return (True, None)
    except Exception as e:
        err_msg = str(e)
        print(f"[Captions] DELIVERY_FAILED order_id={order_id} error={err_msg}")
        traceback.print_exc()
        if "Stories output invalid after retry" in err_msg:
            try:
                order_service.update(order_id, {"stories_generation_status": "failed"})
            except Exception:
                pass
        try:
            order_service.record_delivery_failure(order_id, err_msg)
        except Exception as rec_err:
            print(f"[Captions] record_delivery_failure failed: {rec_err}")
        try:
            order_service.set_failed(order_id)
        except Exception as set_err:
            print(f"[Captions] set_failed also failed: {set_err}")
        return (False, err_msg)


@captions_bp.route("/captions-delivery-status", methods=["GET"])
def captions_delivery_status():
    """
    Diagnostic: check config needed for caption generation and delivery.
    Returns JSON with status (no secrets). In production, requires ?secret=CRON_SECRET when set.
    """
    try:
        if Config.is_production() and getattr(Config, "CRON_SECRET", None):
            if request.args.get("secret", "").strip() != Config.CRON_SECRET:
                return jsonify({"error": "Unauthorized"}), 401
        provider = (getattr(Config, "AI_PROVIDER", None) or "openai").strip().lower()
        ai_ok = False
        ai_msg = ""
        if provider == "anthropic":
            key = (getattr(Config, "ANTHROPIC_API_KEY", None) or "").strip()
            ai_ok = bool(key and len(key) > 20 and key.startswith("sk-ant"))
            ai_msg = "ANTHROPIC_API_KEY: " + ("set" if ai_ok else "missing or invalid")
        else:
            key = (getattr(Config, "OPENAI_API_KEY", None) or "").strip()
            ai_ok = bool(key and len(key) > 20 and key.startswith("sk-"))
            ai_msg = "OPENAI_API_KEY: " + ("set" if ai_ok else "missing or invalid")
        sg_key = (getattr(Config, "SENDGRID_API_KEY", None) or "").strip()
        sg_ok = bool(sg_key and len(sg_key) > 20 and sg_key.startswith("SG."))
        from_email = (getattr(Config, "FROM_EMAIL", None) or "").strip()
        supabase_ok = bool(
            (getattr(Config, "SUPABASE_URL", None) or "").strip()
            and (getattr(Config, "SUPABASE_KEY", None) or "").strip()
        )
        return jsonify({
            "ai_provider": provider,
            "ai_ok": ai_ok,
            "ai_msg": ai_msg,
            "sendgrid_ok": sg_ok,
            "from_email": from_email[:3] + "***" + from_email[-10:] if from_email and "@" in from_email else "(not set)",
            "supabase_ok": supabase_ok,
            "all_ok": ai_ok and sg_ok and bool(from_email) and supabase_ok,
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@captions_bp.route("/captions-deliver-test", methods=["GET"])
def captions_deliver_test():
    """
    Start caption generation + delivery in the background (same as after intake).
    Returns immediately so the request does not time out (502). Generation runs in a thread.
    Protected: if CAPTIONS_DELIVER_TEST_SECRET is set, ?secret=XXX must match.
    Options:
      ?t=TOKEN   — copy the full token from your form link (address bar: .../captions-intake?t=XXX)
      ?session_id=cs_xxx — or use the session_id from the thank-you page URL after payment
      ?sync=1 — run synchronously and return actual result/error (may take 60–90s, can timeout)
      ?secret=XXX — required when CAPTIONS_DELIVER_TEST_SECRET is set in env
    Returns JSON: {"ok": true, "message": "..."} or {"ok": false, "error": "..."}.
    """
    import threading
    from config import Config
    test_secret = (Config.CAPTIONS_DELIVER_TEST_SECRET or "").strip()
    # In production, always require a shared secret so token/session_id alone cannot trigger AI spend.
    if Config.is_production() and not test_secret:
        return jsonify({
            "ok": False,
            "error": "Set CAPTIONS_DELIVER_TEST_SECRET in environment to use this endpoint in production.",
        }), 403
    if test_secret:
        provided = (request.args.get("secret") or "").strip()
        if not provided or provided != test_secret:
            return jsonify({"ok": False, "error": "Missing or invalid ?secret="}), 403
    token = (request.args.get("t") or request.args.get("token") or "").strip()
    session_id = (request.args.get("session_id") or "").strip()
    sync_mode = request.args.get("sync", "").strip().lower() in ("1", "true", "yes")
    if not token and not session_id:
        return jsonify({
            "ok": False,
            "error": "Missing ?t=TOKEN or ?session_id=cs_xxx. Use the token from your form link (the part after t= in the address bar), or the session_id from the thank-you page URL.",
        }), 200
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = None
        if token:
            order = order_service.get_by_token(token)
        if not order and session_id:
            order = order_service.get_by_stripe_session_id(session_id)
        if not order:
            return jsonify({
                "ok": False,
                "error": "Order not found. Use the full token from your form link (address bar: .../captions-intake?t=XXX), or try ?session_id= with the session_id from the thank-you page URL.",
            }), 200
        order_id = order["id"]
        if not order.get("intake"):
            return jsonify({"ok": False, "error": "Please submit the form first."}), 200
        if sync_mode:
            ok, err = _run_generation_and_deliver(order_id, force_redeliver=True)
            if ok:
                return jsonify({
                    "ok": True,
                    "message": "Delivery completed. Check your email (and spam).",
                }), 200
            return jsonify({"ok": False, "error": err or "Delivery failed"}), 200
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,), kwargs={"force_redeliver": True})
        thread.daemon = False
        thread.start()
        return jsonify({
            "ok": True,
            "message": "Generation started. Your captions will be generated and emailed to you in a few minutes (usually 2–5). Check your spam folder if you don't see it.",
        }), 200
    except Exception as e:
        err = _normalize_error(e)
        return jsonify({"ok": False, "error": err}), 200


@captions_bp.route("/captions-delivery-health", methods=["GET"])
def captions_delivery_health():
    """
    Operational snapshot: recent order statuses, auto-retry queue, recent failures.
    Same auth as /api/captions-deliver-test (?secret= when CAPTIONS_DELIVER_TEST_SECRET is set).
    Requires DB columns from database_caption_orders_delivery_retry.sql for full detail.
    """
    test_secret = (getattr(Config, "CAPTIONS_DELIVER_TEST_SECRET", None) or "").strip()
    if Config.is_production() and not test_secret:
        return jsonify({"ok": False, "error": "Set CAPTIONS_DELIVER_TEST_SECRET in environment."}), 403
    if test_secret:
        provided = (request.args.get("secret") or "").strip()
        if not provided or provided != test_secret:
            return jsonify({"ok": False, "error": "Missing or invalid ?secret="}), 403
    try:
        from collections import Counter
        from datetime import datetime, timezone, timedelta

        from services.caption_delivery_recovery import CAPTIONS_MAX_AUTO_DELIVERY_FAILURES
        from services.caption_order_service import CaptionOrderService

        svc = CaptionOrderService()
        recent = (
            svc.client.table(svc.table)
            .select("*")
            .order("updated_at", desc=True)
            .limit(80)
            .execute()
        )
        rows = recent.data or []
        status_counts = Counter((r.get("status") or "").lower() for r in rows)
        stuck = svc.get_orders_needing_first_delivery_recovery(limit=15)
        stuck_summary = []
        for o in stuck:
            stuck_summary.append(
                {
                    "id": str(o.get("id")),
                    "status": o.get("status"),
                    "email": o.get("customer_email"),
                    "delivery_failure_count": o.get("delivery_failure_count"),
                    "delivery_last_error": ((o.get("delivery_last_error") or "")[:200] or None),
                    "has_captions_md": bool((o.get("captions_md") or "").strip()),
                }
            )
        failed_recent = [
            {
                "id": str(r.get("id")),
                "email": r.get("customer_email"),
                "updated_at": r.get("updated_at"),
                "delivery_failure_count": r.get("delivery_failure_count"),
                "delivery_last_error": ((r.get("delivery_last_error") or "")[:300] or None),
            }
            for r in rows
            if (r.get("status") or "").lower() == "failed"
        ][:12]
        now = datetime.now(timezone.utc)
        stale_generating = []
        for r in rows:
            if (r.get("status") or "").lower() != "generating":
                continue
            updated = r.get("updated_at") or r.get("created_at")
            try:
                udt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                if udt.tzinfo is None:
                    udt = udt.replace(tzinfo=timezone.utc)
                if udt < now - timedelta(minutes=30):
                    stale_generating.append(
                        {
                            "id": str(r.get("id")),
                            "email": r.get("customer_email"),
                            "updated_at": r.get("updated_at"),
                        }
                    )
            except Exception:
                pass
        error_counts = Counter(
            ((r.get("delivery_last_error") or "").strip()[:180] for r in rows if (r.get("status") or "").lower() == "failed")
        )
        repeating_failures = [
            {"error": err, "count": count}
            for err, count in error_counts.items()
            if err and count >= 2
        ]
        return jsonify(
            {
                "ok": True,
                "max_auto_delivery_failures_before_stop": CAPTIONS_MAX_AUTO_DELIVERY_FAILURES,
                "recent_sample_size": len(rows),
                "status_counts": dict(status_counts),
                "recovery_queue": stuck_summary,
                "recent_failed": failed_recent,
                "alerts": {
                    "stale_generating_over_30m": stale_generating[:12],
                    "repeating_failed_errors": repeating_failures[:8],
                },
            }
        ), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:500]}), 500


@captions_bp.route("/captions-email-change-audit", methods=["GET"])
def captions_email_change_audit():
    """
    Support endpoint: recent checkout email correction events.
    Protected with CAPTIONS_DELIVER_TEST_SECRET via ?secret=.
    """
    test_secret = (getattr(Config, "CAPTIONS_DELIVER_TEST_SECRET", None) or "").strip()
    if Config.is_production() and not test_secret:
        return jsonify({"ok": False, "error": "Set CAPTIONS_DELIVER_TEST_SECRET in environment."}), 403
    if test_secret:
        provided = (request.args.get("secret") or "").strip()
        if not provided or provided != test_secret:
            return jsonify({"ok": False, "error": "Missing or invalid ?secret="}), 403
    try:
        from services.caption_order_service import CaptionOrderService

        limit = max(1, min(100, int(request.args.get("limit", 30) or 30)))
        svc = CaptionOrderService()
        recent = (
            svc.client.table(svc.table)
            .select("id,customer_email,status,updated_at,email_change_events")
            .order("updated_at", desc=True)
            .limit(200)
            .execute()
        )
        rows = recent.data or []
        events = []
        for row in rows:
            row_events = row.get("email_change_events") or []
            if not isinstance(row_events, list):
                continue
            for ev in row_events:
                if not isinstance(ev, dict):
                    continue
                events.append(
                    {
                        "order_id": str(row.get("id") or ""),
                        "current_email": row.get("customer_email"),
                        "order_status": row.get("status"),
                        "at": ev.get("at"),
                        "old_email": ev.get("old_email"),
                        "new_email": ev.get("new_email"),
                        "ip": ev.get("ip"),
                        "user_agent": ev.get("user_agent"),
                        "source": ev.get("source"),
                    }
                )
        events.sort(key=lambda e: e.get("at") or "", reverse=True)
        return jsonify(
            {
                "ok": True,
                "count": min(limit, len(events)),
                "events": events[:limit],
            }
        ), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:500]}), 500


@captions_bp.route("/captions-redeliver-order", methods=["POST"])
def captions_redeliver_order():
    """
    Support endpoint: safely re-trigger delivery for a specific order.
    Protected with CAPTIONS_DELIVER_TEST_SECRET in production.
    JSON body: {"order_id":"...", "captions_only": true|false}
    """
    test_secret = (getattr(Config, "CAPTIONS_DELIVER_TEST_SECRET", None) or "").strip()
    if Config.is_production() and not test_secret:
        return jsonify({"ok": False, "error": "Set CAPTIONS_DELIVER_TEST_SECRET in environment."}), 403
    provided = (request.args.get("secret") or "").strip()
    if test_secret and (not provided or provided != test_secret):
        return jsonify({"ok": False, "error": "Missing or invalid ?secret="}), 403
    data = request.get_json(silent=True) or {}
    order_id = str(data.get("order_id") or "").strip()
    captions_only = bool(data.get("captions_only"))
    if not order_id:
        return jsonify({"ok": False, "error": "Missing order_id"}), 400
    try:
        from services.caption_order_service import CaptionOrderService

        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        if not (order.get("intake") or {}):
            return jsonify({"ok": False, "error": "Order has no intake yet"}), 400
        ok, err = _run_generation_and_deliver(
            order_id,
            force_redeliver=True,
            force_captions_only=captions_only,
        )
        if ok:
            return jsonify({"ok": True, "message": "Redelivery completed."}), 200
        return jsonify({"ok": False, "error": err or "Redelivery failed"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": _normalize_error(e)}), 500


@captions_bp.route("/captions-intake", methods=["POST"])
def captions_intake_submit():
    """
    Submit intake for a 30 Days Captions order (identified by token).
    Saves intake and starts generation in background; returns immediately.
    """
    import traceback

    try:
        # force=True parses JSON even when Content-Type is missing/wrong (e.g. proxy)
        data = request.get_json(silent=True, force=True) or request.form or {}
    except Exception as parse_err:
        print(f"[captions-intake] JSON parse error: {parse_err}")
        return jsonify({"error": "Invalid request body. Please try again."}), 400

    try:
        return _captions_intake_submit_impl(data)
    except Exception as e:
        traceback.print_exc()
        detail = str(e)
        payload = {"error": "Internal server error"}
        # Include detail only when SHOW_500_DETAIL=1 and NOT production
        if os.environ.get("SHOW_500_DETAIL") == "1" and not Config.is_production():
            payload["detail"] = f"{type(e).__name__}: {detail}"
        return jsonify(payload), 500


def _captions_intake_submit_impl(data):
    from services.caption_order_service import CaptionOrderService
    import threading

    if not data:
        return jsonify({"error": "Please fill in the form."}), 400

    token = (data.get("token") or data.get("t") or "").strip()
    if not token:
        return jsonify({"error": "Missing token. Use the link from your order email."}), 400

    business_name = (data.get("business_name") or "").strip()
    if not business_name:
        return jsonify({"error": "Business name is required. Please enter your business name."}), 400

    voice_words_raw = (data.get("voice_words") or "").strip()
    if not voice_words_raw:
        return jsonify({"error": "Voice is required. Choose at least one tone or add words in Other."}), 400

    try:
        order_service = CaptionOrderService()
    except ValueError:
        return jsonify({"error": "Service unavailable"}), 503
    order = order_service.get_by_token(token)
    if not order:
        return jsonify({"error": "Invalid or expired link. Use the link from your order email."}), 404

    order_has_stories = bool(order.get("include_stories"))
    order_platforms_count = max(1, int(order.get("platforms_count", 1)))
    subscription_id = (order.get("stripe_subscription_id") or "").strip()

    include_hashtags = data.get("include_hashtags")
    if isinstance(include_hashtags, bool):
        pass
    elif isinstance(include_hashtags, str):
        include_hashtags = include_hashtags.strip().lower() in ("true", "1", "yes", "on")
    else:
        include_hashtags = True
    try:
        hashtag_min = max(1, min(30, int(data.get("hashtag_min") or 3)))
    except (TypeError, ValueError):
        hashtag_min = 3
    try:
        hashtag_max = max(0, min(30, int(data.get("hashtag_max") or 10)))
    except (TypeError, ValueError):
        hashtag_max = 10
    if hashtag_min > hashtag_max:
        hashtag_max = hashtag_min

    align_flag = data.get("align_stories_to_captions") or data.get("align_stories")
    if isinstance(align_flag, str):
        align_flag = align_flag.strip().lower() in ("1", "true", "yes", "on")
    else:
        align_flag = bool(align_flag)

    intake = {
        "business_name": (data.get("business_name") or "").strip(),
        "business_type": (data.get("business_type") or "").strip(),
        "offer_one_line": (data.get("offer_one_line") or "").strip(),
        "operating_hours": (data.get("operating_hours") or "").strip(),
        "audience": (data.get("audience") or "").strip(),
        "consumer_age_range": (data.get("consumer_age_range") or "").strip(),
        "audience_cares": (data.get("audience_cares") or "").strip(),
        "voice_words": voice_words_raw,
        "voice_avoid": (data.get("voice_avoid") or "").strip(),
        "platform": (data.get("platform") or "").strip(),
        "platform_habits": (data.get("platform_habits") or "").strip(),
        "include_hashtags": include_hashtags,
        "hashtag_min": hashtag_min,
        "hashtag_max": hashtag_max,
        "goal": (data.get("goal") or "").strip(),
        "launch_event_description": (data.get("launch_event_description") or "").strip(),
        "usual_topics": (data.get("usual_topics") or "").strip(),
        "caption_examples": (data.get("caption_examples") or "").strip(),
        "facts_guardrails": (data.get("facts_guardrails") or "").strip(),
        "vary_ig_fb_caption_length": bool(data.get("vary_ig_fb_caption_length")),
        "caption_language": (data.get("caption_language") or "English (UK)").strip(),
        "include_stories": order_has_stories and (bool(data.get("include_stories")) or bool((order.get("intake") or {}).get("include_stories"))),
        "align_stories_to_captions": align_flag,
    }
    if not (intake.get("platform") or "").strip():
        fb = (order.get("selected_platforms") or "").strip()
        if not fb and order_platforms_count == 1:
            fb = "Instagram & Facebook"
        if fb:
            intake["platform"] = fb

    launch_window_error = _validate_launch_event_window(
        intake.get("launch_event_description") or "",
        (order.get("pack_start_date") or "").strip(),
    )
    if launch_window_error:
        return jsonify({"error": launch_window_error}), 400

    form_wants_stories = bool(data.get("include_stories"))
    if form_wants_stories and not order_has_stories:
        # Get pack sooner / Update preferences: hub passes upgrade_stories=1 so Story Ideas appear selected
        # before checkout; billing runs on the hub, not captions-upgrade. Allow save — merged intake keeps
        # include_stories false until the subscription row is updated after payment.
        prepare_pps = bool(data.get("prepare_pack_sooner_edit"))
        if not (subscription_id and prepare_pps):
            base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
            if base and not base.startswith("http"):
                base = "https://" + base
            return_url = quote(f"{base}/captions-intake?t={token}") if base else ""
            upgrade_url = f"{base}/captions-upgrade?token={quote(token)}&stories=1" + (f"&return_url={return_url}" if return_url else "") if base else f"/captions-upgrade?token={quote(token)}&stories=1"
            return jsonify({
                "error": "To include Story Ideas you need to add the add-on. Please confirm and accept the new price. Note: Story Ideas added later are delivered with your next caption pack, not instantly.",
                "upgrade_required": True,
                "upgrade_type": "stories",
                "upgrade_url": upgrade_url,
            }), 400

    # Downgrade: reducing platforms or removing Stories requires accepting new (lower) price.
    # Only applies to subscriptions (one-off orders can't change price).
    form_platforms_count = 1
    platform_val = (intake.get("platform") or "").strip()
    if platform_val and "," in platform_val:
        platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
        form_platforms_count = max(1, len(platform_parts))
    else:
        form_platforms_count = 1 if platform_val else 1
    downgrade_platforms = form_platforms_count < order_platforms_count
    downgrade_stories = order_has_stories and not form_wants_stories
    if subscription_id and (downgrade_platforms or downgrade_stories):
        new_platforms = form_platforms_count
        new_stories = form_wants_stories
        order_currency = (order.get("currency") or "gbp").strip().lower()
        if order_currency not in ("gbp", "usd", "eur"):
            order_currency = "gbp"
        try:
            from api.billing_routes import _subscription_monthly_price
            new_sym, new_total = _subscription_monthly_price(order_currency, new_platforms, new_stories)
        except Exception:
            new_sym = "£"
            new_total = 79 + (new_platforms - 1) * 19 + (17 if new_stories else 0)
        return jsonify({
            "error": "You're reducing your plan. Please accept the new price before we save your changes. Your next invoice will reflect the lower amount.",
            "downgrade_required": True,
            "new_platforms": new_platforms,
            "new_stories": new_stories,
            "new_price": new_total,
            "new_price_symbol": new_sym,
        }), 400

    order_id = order["id"]
    status = order.get("status") or ""

    # First intake OR retry when delivery never completed (failed worker, SendGrid error, stuck "generating")
    from services.caption_delivery_recovery import row_needs_first_delivery_retry

    if status == "awaiting_intake" or row_needs_first_delivery_retry(
        order, intake_completed_grace_seconds=0
    ):
        platform_val = (intake.get("platform") or "").strip()
        if platform_val and "," in platform_val:
            platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
            if len(platform_parts) > order_platforms_count:
                base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
                if base and not base.startswith("http"):
                    base = "https://" + base
                return_url = quote(f"{base}/captions-intake?t={token}") if base else ""
                upgrade_url = f"{base}/captions-upgrade?token={quote(token)}&platforms={len(platform_parts)}" + (f"&return_url={return_url}" if return_url else "") if base else f"/captions-upgrade?token={quote(token)}&platforms={len(platform_parts)}"
                return jsonify({
                    "error": f"You selected {len(platform_parts)} platforms but your order includes {order_platforms_count}. To get more platforms, please confirm and accept the new price. Extra platforms are delivered with your next caption pack, not instantly.",
                    "upgrade_required": True,
                    "upgrade_type": "platforms",
                    "upgrade_url": upgrade_url,
                }), 400
        # Upgrade-from-one-off: first deliver the already-paid one-off pack (if still pending),
        # then schedule the first subscription pack ~30 days later to avoid overlap.
        upgraded_from = (order.get("upgraded_from_token") or "").strip()
        scheduled_delivery_at = None
        scheduled_date_str = None
        deliver_base_one_off_now = False
        base_one_off_id = None
        base_one_off_delivered = False
        if upgraded_from and order.get("stripe_subscription_id"):
            one_off = order_service.get_by_token(upgraded_from)
            if one_off:
                base_one_off_id = one_off.get("id")
                base_one_off_delivered = bool(one_off.get("status") == "delivered" or one_off.get("delivered_at"))
                try:
                    from datetime import datetime, timedelta, timezone
                    if base_one_off_delivered:
                        delivered_at_raw = one_off.get("delivered_at") or one_off.get("updated_at") or one_off.get("created_at")
                        if delivered_at_raw:
                            if isinstance(delivered_at_raw, str):
                                dt = datetime.fromisoformat(delivered_at_raw.replace("Z", "+00:00"))
                            else:
                                dt = delivered_at_raw
                            if getattr(dt, "tzinfo", None) is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            scheduled = dt + timedelta(days=30)
                        else:
                            scheduled = datetime.now(timezone.utc) + timedelta(days=30)
                    else:
                        # Base one-off not delivered yet: always deliver it after this save.
                        # (Prefilled intake from the one-off or any non-awaiting_intake status used to skip
                        # the trigger while we still returned early with only scheduled_delivery_at — no PDFs.)
                        scheduled = datetime.now(timezone.utc) + timedelta(days=30)
                        deliver_base_one_off_now = True
                    scheduled_delivery_at = scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")
                    scheduled_date_str = scheduled.strftime("%d %B %Y")
                except Exception:
                    pass
        if not order_service.save_intake(order_id, intake, scheduled_delivery_at=scheduled_delivery_at):
            print(f"[captions_intake] save_intake FAILED for subscription order_id={order_id} token_tail=...{(order.get('token') or '')[-8:]}")
            return jsonify({"error": "Failed to save. Please try again."}), 500
        if deliver_base_one_off_now and base_one_off_id:
            try:
                # Reuse submitted intake for the original one-off so customer receives the pack they already paid for.
                if order_service.save_intake(base_one_off_id, intake):
                    thread_base = threading.Thread(target=_run_generation_and_deliver, args=(base_one_off_id,))
                    thread_base.daemon = False
                    thread_base.start()
                else:
                    print(
                        f"[captions_intake] save_intake FAILED for base one-off order_id={base_one_off_id} "
                        f"(subscription {order_id} saved). Customer may not receive paid one-off pack — retry save or support."
                    )
            except Exception as e:
                print(f"[captions_intake] base one-off immediate delivery trigger failed: {e}")
        if scheduled_delivery_at and scheduled_date_str:
            is_subscription = True
            customer_email = (order.get("customer_email") or "").strip().lower()
            customer_has_account = False
            if customer_email:
                try:
                    from services.customer_auth_service import CustomerAuthService
                    auth_svc = CustomerAuthService()
                    customer_has_account = auth_svc.get_by_email(customer_email) is not None
                except Exception:
                    pass
            msg = f"Thanks. Your first subscription pack will be delivered on {scheduled_date_str} — 30 days after your one-off pack, so you get continuous content with no overlap."
            if deliver_base_one_off_now:
                msg = "Thanks. We are delivering your one-off pack now, and your first subscription pack will be delivered on " + scheduled_date_str + " (about 30 days later) so you get continuous content with no overlap."
            return jsonify({
                "success": True,
                "message": msg,
                "scheduled_delivery_date": scheduled_date_str,
                "customer_email": order.get("customer_email") or "",
                "is_subscription": True,
                "customer_has_account": customer_has_account,
            }), 200
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = False
        thread.start()
        is_subscription = bool(order.get("stripe_subscription_id"))
        customer_email = (order.get("customer_email") or "").strip().lower()
        customer_has_account = False
        if customer_email:
            try:
                from services.customer_auth_service import CustomerAuthService
                auth_svc = CustomerAuthService()
                customer_has_account = auth_svc.get_by_email(customer_email) is not None
            except Exception:
                pass
        return jsonify({
            "success": True,
            "message": "Thanks. We're generating your 30 captions now. You'll receive them by email within a few minutes.",
            "customer_email": order.get("customer_email") or "",
            "is_subscription": is_subscription,
            "customer_has_account": customer_has_account,
        }), 200

    # Edit mode: order already has intake (intake_completed, generating, delivered)
    if order.get("intake") and status in ("intake_completed", "generating", "delivered"):
        # One-off: no further intake updates via this API — use account (view) + subscription to edit.
        if not (order.get("stripe_subscription_id") or "").strip():
            if order_service.has_subscription_upgraded_from_oneoff_token(token):
                return jsonify({
                    "error": (
                        "You’re on the link for your old one-off pack, which was already used to start your subscription. "
                        "We can’t save edits against that one-off order anymore. "
                        "To change your brief for future packs: log in → Account → Edit form → open the row for your subscription (not the one-off)."
                    ),
                    "oneoff_edit_blocked": True,
                    "upgraded_to_subscription": True,
                    "account_edit_form_url": "/account/edit-form",
                }), 400
            # Account → Upgrade → Edit form (?edit=1): save intake to this one-off before subscription checkout (logged-in customer only).
            oue = data.get("oneoff_upgrade_edit")
            if isinstance(oue, str):
                oneoff_upgrade_edit = oue.strip().lower() in ("1", "true", "yes", "on")
            else:
                oneoff_upgrade_edit = bool(oue)
            if oneoff_upgrade_edit:
                from api.auth_routes import get_current_customer

                customer = get_current_customer()
                order_email = (order.get("customer_email") or "").strip().lower()
                cust_email = (customer.get("email") or "").strip().lower() if customer else ""
                if customer and order_email and cust_email == order_email:
                    if not order_service.update_intake_only(order_id, intake):
                        return jsonify({"error": "Failed to update. Please try again."}), 500
                    customer_has_account = True
                    return jsonify({
                        "success": True,
                        "message": (
                            "Your form has been updated. Continue from Account → Upgrade to complete subscription checkout, "
                            "or use Send details again if you’re still on this page."
                        ),
                        "customer_email": order.get("customer_email") or "",
                        "is_subscription": False,
                        "customer_has_account": customer_has_account,
                    }), 200
                return jsonify({
                    "error": "Log in with the same email as this order to save changes before subscribing.",
                    "oneoff_edit_blocked": True,
                }), 403
            base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
            if base and not base.startswith("http"):
                base = "https://" + base
            qtok = quote(token, safe="")
            upgrade_account_url = f"{base}/account/upgrade?base={qtok}" if base else f"/account/upgrade?base={qtok}"
            return jsonify({
                "error": (
                    "This page is the link for your one-off pack, which is already complete. "
                    "We can’t save new answers here—that link only applied to that single purchase. "
                    "To move to a subscription and edit your brief for ongoing monthly packs: log in, go to Account → Upgrade, and finish subscription checkout. "
                    "After that, use Account → Edit form and choose your subscription row to update your details (not this one-off link). "
                    "Want another month without subscribing? Buy another one-off from the pricing page."
                ),
                "oneoff_edit_blocked": True,
                "upgrade_account_url": upgrade_account_url,
            }), 400
        platform_val = (intake.get("platform") or "").strip()
        if platform_val and "," in platform_val:
            platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
            if len(platform_parts) > order_platforms_count:
                base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
                if base and not base.startswith("http"):
                    base = "https://" + base
                return_url = quote(f"{base}/captions-intake?t={token}") if base else ""
                upgrade_url = f"{base}/captions-upgrade?token={quote(token)}&platforms={len(platform_parts)}" + (f"&return_url={return_url}" if return_url else "") if base else f"/captions-upgrade?token={quote(token)}&platforms={len(platform_parts)}"
                return jsonify({
                    "error": f"You selected {len(platform_parts)} platforms but your order includes {order_platforms_count}. To get more platforms, please confirm and accept the new price. Extra platforms are delivered with your next caption pack, not instantly.",
                    "upgrade_required": True,
                    "upgrade_type": "platforms",
                    "upgrade_url": upgrade_url,
                }), 400
        if not order_service.update_intake_only(order_id, intake):
            return jsonify({"error": "Failed to update. Please try again."}), 500
        customer_email = (order.get("customer_email") or "").strip().lower()
        customer_has_account = False
        if customer_email:
            try:
                from services.customer_auth_service import CustomerAuthService
                auth_svc = CustomerAuthService()
                customer_has_account = auth_svc.get_by_email(customer_email) is not None
            except Exception:
                pass
        return jsonify({
            "success": True,
            "message": "Your form has been updated. Your changes will be reflected in your next captions and stories pack, not in packs already delivered.",
            "customer_email": order.get("customer_email") or "",
            "is_subscription": bool(order.get("stripe_subscription_id")),
            "customer_has_account": customer_has_account,
        }), 200

    return jsonify({"error": "This order has already been completed or is in progress."}), 400


@captions_bp.route("/captions-download", methods=["GET"])
def captions_download():
    """
    Download captions or stories PDF for a delivered order. Requires logged-in customer;
    order must belong to customer's email.
    ?t=TOKEN → captions PDF. ?t=TOKEN&type=stories → stories PDF (if order had Stories add-on).
    """
    from api.auth_routes import get_current_customer

    customer = get_current_customer()
    if not customer:
        return redirect("/login?next=/account"), 302
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Invalid customer"}), 400
    token = (request.args.get("t") or request.args.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Missing token (use ?t=TOKEN from your order)"}), 400
    download_type = (request.args.get("type") or "captions").strip().lower()
    inline = request.args.get("inline", "").strip().lower() in ("1", "true", "yes")
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_token(token)
    except Exception:
        return jsonify({"error": "Could not load order"}), 500
    if not order:
        return jsonify({"error": "Order not found"}), 404
    order_email = (order.get("customer_email") or "").strip().lower()
    if order_email != email:
        return jsonify({"error": "This order does not belong to your account"}), 403
    if order.get("status") != "delivered":
        return jsonify({"error": "Captions not ready yet (status: {})".format(order.get("status", "—"))}), 400
    captions_md = order.get("captions_md")
    if not captions_md:
        return jsonify({"error": "Captions file not found"}), 404
    from datetime import datetime
    date_str = (order.get("created_at") or "")[:10] if order.get("created_at") else datetime.utcnow().strftime("%Y-%m-%d")
    intake = order.get("intake") or {}
    business_name = _filename_safe((intake.get("business_name") or "").strip())
    name_label = business_name if business_name else "Pack"

    if download_type == "stories":
        if not order.get("include_stories"):
            return jsonify({"error": "This order did not include the Stories add-on"}), 400
        import base64
        stored_b64 = (order.get("stories_pdf_base64") or "").strip()
        if stored_b64:
            try:
                pdf_bytes = base64.b64decode(stored_b64)
            except Exception:
                pdf_bytes = None
        else:
            pdf_bytes = None
        if not pdf_bytes:
            try:
                from services.caption_pdf import build_stories_pdf, get_logo_path
                logo_path = get_logo_path()
                pdf_bytes = build_stories_pdf(
                    captions_md, logo_path=logo_path, pack_start_date=date_str
                )
            except Exception as e:
                return jsonify({"error": "Could not build Stories PDF: {}".format(str(e))}), 500
        if not pdf_bytes:
            return jsonify({"error": "Stories PDF not available for this pack"}), 404
        filename = f"{name_label}_Stories_{date_str}.pdf"
        disp = "inline" if inline else "attachment"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "{}; filename={}".format(disp, filename)},
        )

    # Captions PDF (default)
    import base64
    stored_captions_b64 = (order.get("captions_pdf_base64") or "").strip()
    if stored_captions_b64:
        try:
            pdf_bytes = base64.b64decode(stored_captions_b64)
        except Exception:
            pdf_bytes = None
    else:
        pdf_bytes = None
    if not pdf_bytes:
        try:
            from services.caption_pdf import build_caption_pdf, get_logo_path
            logo_path = get_logo_path()
            pdf_bytes = build_caption_pdf(
                captions_md, logo_path=logo_path, pack_start_date=date_str
            )
        except Exception as e:
            return jsonify({"error": "Could not build PDF: {}".format(str(e))}), 500
    filename = f"{name_label}_Captions_{date_str}.pdf"
    disp = "inline" if inline else "attachment"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "{}; filename={}".format(disp, filename)},
    )


@captions_bp.route("/captions-download-public", methods=["GET"])
def captions_download_public():
    """
    Download captions or stories PDF for delivered orders using a signed, expiring URL.
    This is for backup links in delivery emails for users without accounts.
    Query: ?t=TOKEN&type=captions|stories&exp=UNIX_TS&sig=HMAC_HEX
    """
    token = (request.args.get("t") or request.args.get("token") or "").strip()
    download_type = (request.args.get("type") or "captions").strip().lower()
    sig = (request.args.get("sig") or "").strip()
    try:
        exp_ts = int(request.args.get("exp") or "0")
    except Exception:
        exp_ts = 0
    if not token:
        return jsonify({"error": "Missing token"}), 400
    if download_type not in ("captions", "stories"):
        return jsonify({"error": "Invalid type"}), 400
    if not _verify_public_download_signature(token, download_type, exp_ts, sig):
        return jsonify({"error": "This backup link is invalid or expired."}), 403
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_token(token)
    except Exception:
        return jsonify({"error": "Could not load order"}), 500
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.get("status") != "delivered":
        return jsonify({"error": "Captions are not ready yet."}), 400
    captions_md = order.get("captions_md")
    if not captions_md:
        return jsonify({"error": "Captions file not found"}), 404
    from datetime import datetime
    date_str = (order.get("created_at") or "")[:10] if order.get("created_at") else datetime.utcnow().strftime("%Y-%m-%d")
    intake = order.get("intake") or {}
    business_name = _filename_safe((intake.get("business_name") or "").strip())
    name_label = business_name if business_name else "Pack"
    if download_type == "stories":
        if not order.get("include_stories"):
            return jsonify({"error": "This order did not include the Stories add-on"}), 400
        import base64
        stored_b64 = (order.get("stories_pdf_base64") or "").strip()
        if stored_b64:
            try:
                pdf_bytes = base64.b64decode(stored_b64)
            except Exception:
                pdf_bytes = None
        else:
            pdf_bytes = None
        if not pdf_bytes:
            try:
                from services.caption_pdf import build_stories_pdf, get_logo_path
                logo_path = get_logo_path()
                pdf_bytes = build_stories_pdf(captions_md, logo_path=logo_path, pack_start_date=date_str)
            except Exception as e:
                return jsonify({"error": "Could not build Stories PDF: {}".format(str(e))}), 500
        if not pdf_bytes:
            return jsonify({"error": "Stories PDF not available for this pack"}), 404
        filename = f"{name_label}_Stories_{date_str}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename={}".format(filename)},
        )
    import base64
    stored_captions_b64 = (order.get("captions_pdf_base64") or "").strip()
    if stored_captions_b64:
        try:
            pdf_bytes = base64.b64decode(stored_captions_b64)
        except Exception:
            pdf_bytes = None
    else:
        pdf_bytes = None
    if not pdf_bytes:
        try:
            from services.caption_pdf import build_caption_pdf, get_logo_path
            logo_path = get_logo_path()
            pdf_bytes = build_caption_pdf(captions_md, logo_path=logo_path, pack_start_date=date_str)
        except Exception as e:
            return jsonify({"error": "Could not build PDF: {}".format(str(e))}), 500
    filename = f"{name_label}_Captions_{date_str}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)},
    )


@captions_bp.route("/captions-resend-delivery", methods=["POST"])
def captions_resend_delivery():
    """
    Resend delivery email for a delivered pack using stored artifacts when available.
    Requires login and ownership of the order.
    Body: { "token": "..." }  or  { "order_id": "..." }
    """
    from api.auth_routes import get_current_customer
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService, _captions_delivery_email_html
    import base64

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    try:
        data = request.get_json() or {}
        token = (data.get("token") or "").strip()
        order_id = (data.get("order_id") or "").strip()
        if not token and not order_id:
            return jsonify({"ok": False, "error": "token or order_id required"}), 400

        order_service = CaptionOrderService()
        order = order_service.get_by_token(token) if token else order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403
        if order.get("status") != "delivered":
            return jsonify({"ok": False, "error": "Only delivered packs can be resent"}), 400

        captions_md = (order.get("captions_md") or "").strip()
        if not captions_md:
            return jsonify({"ok": False, "error": "No captions content saved for this pack"}), 404

        # Primary artifact: saved captions PDF; fallback to regenerate.
        captions_pdf = None
        stored_captions_b64 = (order.get("captions_pdf_base64") or "").strip()
        if stored_captions_b64:
            try:
                captions_pdf = base64.b64decode(stored_captions_b64)
            except Exception:
                captions_pdf = None
        if not captions_pdf:
            from services.caption_pdf import build_caption_pdf, get_logo_path
            date_str = (order.get("created_at") or "")[:10] or time.strftime("%Y-%m-%d")
            captions_pdf = build_caption_pdf(captions_md, logo_path=get_logo_path(), pack_start_date=date_str)

        include_stories = bool(order.get("include_stories"))
        extra_attachments = []
        if include_stories:
            stories_pdf = None
            stored_stories_b64 = (order.get("stories_pdf_base64") or "").strip()
            if stored_stories_b64:
                try:
                    stories_pdf = base64.b64decode(stored_stories_b64)
                except Exception:
                    stories_pdf = None
            if not stories_pdf:
                try:
                    from services.caption_pdf import build_stories_pdf, get_logo_path
                    date_str = (order.get("created_at") or "")[:10] or time.strftime("%Y-%m-%d")
                    stories_pdf = build_stories_pdf(
                        captions_md, logo_path=get_logo_path(), pack_start_date=date_str
                    )
                except Exception:
                    stories_pdf = None
            if stories_pdf:
                extra_attachments.append({
                    "filename": "30_Days_Story_Ideas.pdf",
                    "content": stories_pdf,
                    "mime_type": "application/pdf",
                })

        safe_token = (order.get("token") or "").strip()
        base = (Config.BASE_URL or "").strip().rstrip("/")
        if not base.startswith("http"):
            base = "https://www.lumo22.com"
        backup_captions_url = _build_public_download_url(base, safe_token, "captions")
        backup_stories_url = _build_public_download_url(base, safe_token, "stories") if include_stories else ""
        has_sub = bool(order.get("stripe_subscription_id"))

        if extra_attachments:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions and 30 Days of Story Ideas are attached.\n\n"
                "If attachments don't appear in your inbox, use your backup download link(s):\n"
                f"For your security, these backup links expire within {_public_download_expiry_hours()} hour(s).\n"
                f"{backup_captions_url}\n{backup_stories_url}\n\n"
            )
        else:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions are attached.\n\n"
                "If attachments don't appear in your inbox, use your backup download link:\n"
                f"For your security, this backup link expires within {_public_download_expiry_hours()} hour(s).\n"
                f"{backup_captions_url}\n\n"
            )
        if has_sub:
            body += "Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account -> Manage subscription.\n\n"
        body += "Lumo 22\n"

        intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
        business_name = (intake.get("business_name") or "").strip() if intake else ""
        html_body = _captions_delivery_email_html(
            bool(extra_attachments),
            has_subscription=has_sub,
            backup_captions_url=backup_captions_url,
            backup_stories_url=backup_stories_url,
            backup_link_expiry_hours=_public_download_expiry_hours(),
            business_name=business_name or None,
        )
        notif = NotificationService()
        subject = "Your 30 Days of Social Media Captions"
        if business_name:
            subject = f"{subject} — {business_name}"
        ok, send_error = notif.send_email_with_attachment(
            email,
            subject,
            body,
            filename="30_Days_Captions.pdf",
            file_content_bytes=captions_pdf,
            mime_type="application/pdf",
            extra_attachments=extra_attachments if extra_attachments else None,
            html_content=html_body,
        )
        if not ok:
            return jsonify({"ok": False, "error": send_error or "Could not resend email"}), 500
        return jsonify({"ok": True, "message": "Delivery email resent"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _pause_info_from_subscription(sub) -> dict:
    """Build pause + cancellation dict from a Stripe Subscription object (already retrieved)."""
    from datetime import datetime

    out = {
        "paused": False,
        "resumes_at": None,
        "cancel_at_period_end": False,
        "cancelled_now": False,
        "ends_at": None,
        "next_pack_due": None,
    }
    pc = sub.get("pause_collection")
    if pc and isinstance(pc, dict):
        resumes_ts = pc.get("resumes_at")
        if resumes_ts:
            try:
                dt = datetime.utcfromtimestamp(resumes_ts)
                out["paused"] = True
                out["resumes_at"] = dt.strftime("%d %b %Y")
            except (TypeError, ValueError, OSError):
                out["paused"] = True
        else:
            out["paused"] = True
    if sub.get("cancel_at_period_end"):
        out["cancel_at_period_end"] = True
        cancel_ts = sub.get("cancel_at") or sub.get("current_period_end")
        if cancel_ts:
            try:
                dt = datetime.utcfromtimestamp(cancel_ts)
                out["ends_at"] = dt.strftime("%d %b %Y")
            except (TypeError, ValueError, OSError):
                pass
    if str(sub.get("status") or "").strip().lower() == "canceled":
        out["cancelled_now"] = True
        ended_ts = sub.get("ended_at") or sub.get("canceled_at") or sub.get("cancel_at")
        if ended_ts:
            try:
                dt = datetime.utcfromtimestamp(ended_ts)
                out["ends_at"] = dt.strftime("%d %b %Y")
            except (TypeError, ValueError, OSError):
                pass
    if not out["cancelled_now"]:
        cpe = sub.get("current_period_end")
        if cpe is not None:
            try:
                dt_end = datetime.utcfromtimestamp(int(cpe))
                out["next_pack_due"] = dt_end.strftime("%d %b %Y")
            except (TypeError, ValueError, OSError):
                pass
    return out


def _get_subscription_pause_info(stripe_subscription_id: str):
    """Fetch subscription from Stripe; return pause + cancellation state for dashboard badges."""
    from api.stripe_utils import is_valid_stripe_subscription_id
    if not stripe_subscription_id or not Config.STRIPE_SECRET_KEY or not is_valid_stripe_subscription_id(stripe_subscription_id):
        return None
    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(stripe_subscription_id.strip())
        return _pause_info_from_subscription(sub)
    except Exception:
        return None


@captions_bp.route("/captions/pause-subscription", methods=["POST"])
def captions_pause_subscription():
    """
    Pause caption subscription for 1 month. Requires login.
    Body: { "order_id": "..." }
    """
    from api.auth_routes import get_current_customer
    from datetime import datetime, timedelta
    import stripe

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        if not order_id:
            return jsonify({"ok": False, "error": "order_id required"}), 400

        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
        from api.stripe_utils import is_valid_stripe_subscription_id
        if not is_valid_stripe_subscription_id(sub_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(sub_id)
        pc = sub.get("pause_collection")
        if pc and isinstance(pc, dict) and pc.get("resumes_at"):
            return jsonify({
                "ok": False,
                "error": "Subscription is already paused",
                "resumes_at": pc.get("resumes_at"),
            }), 400

        resumes_at = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        stripe.Subscription.modify(
            sub_id,
            pause_collection={"behavior": "void", "resumes_at": resumes_at},
        )
        resumes_date = datetime.utcfromtimestamp(resumes_at).strftime("%d %b %Y")
        return jsonify({
            "ok": True,
            "resumes_at": resumes_date,
        }), 200
    except stripe.StripeError as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@captions_bp.route("/captions/resume-subscription", methods=["POST"])
def captions_resume_subscription():
    """
    Resume a paused caption subscription. Requires login.
    Body: { "order_id": "..." }
    """
    from api.auth_routes import get_current_customer
    import stripe

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        if not order_id:
            return jsonify({"ok": False, "error": "order_id required"}), 400

        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
        from api.stripe_utils import is_valid_stripe_subscription_id
        if not is_valid_stripe_subscription_id(sub_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(sub_id)
        pc = sub.get("pause_collection")
        if not pc or not isinstance(pc, dict) or not pc.get("resumes_at"):
            return jsonify({"ok": False, "error": "Subscription is not paused"}), 400

        # We pause via pause_collection (behavior=void), not the Pause endpoint.
        # To resume, unset pause_collection via modify; Subscription.resume()
        # only works when status is "paused" (different mechanism).
        stripe.Subscription.modify(sub_id, pause_collection="")
        return jsonify({"ok": True, "message": "Subscription resumed."}), 200
    except stripe.error.InvalidRequestError as e:
        # Subscription may be cancelled, deleted, or in unexpected state
        msg = str(e).lower()
        if "no such" in msg or "deleted" in msg or "canceled" in msg or "cancel" in msg:
            return jsonify({"ok": False, "error": "This subscription is no longer active and cannot be resumed."}), 400
        return jsonify({"ok": False, "error": (str(e) or "Could not resume")[:200]}), 400
    except stripe.error.StripeError as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@captions_bp.route("/captions/restart-subscription", methods=["POST"])
def captions_restart_subscription():
    """
    Restart a subscription that was cancelled at period end.
    Sets cancel_at_period_end=False so it will renew again.
    Body: { "order_id": "..." }
    """
    from api.auth_routes import get_current_customer
    import stripe

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        if not order_id:
            return jsonify({"ok": False, "error": "order_id required"}), 400

        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
        from api.stripe_utils import is_valid_stripe_subscription_id
        if not is_valid_stripe_subscription_id(sub_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(sub_id)
        if not sub.get("cancel_at_period_end"):
            return jsonify({"ok": False, "error": "Subscription is not scheduled for cancellation"}), 400

        stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
        return jsonify({"ok": True, "message": "Subscription resumed. It will renew at the end of your billing period."}), 200
    except stripe.error.InvalidRequestError as e:
        msg = str(e).lower()
        if "no such" in msg or "deleted" in msg or "canceled" in msg or "cancel" in msg:
            return jsonify({"ok": False, "error": "This subscription is no longer active."}), 400
        return jsonify({"ok": False, "error": (str(e) or "Could not resume")[:200]}), 400
    except stripe.error.StripeError as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@captions_bp.route("/captions/cancel-subscription", methods=["POST"])
def captions_cancel_subscription():
    """
    Cancel a caption subscription immediately. Requires login.
    Body: { "order_id": "..." }
    """
    from api.auth_routes import get_current_customer
    import stripe

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        if not order_id:
            return jsonify({"ok": False, "error": "order_id required"}), 400

        from services.caption_order_service import CaptionOrderService
        from api.stripe_utils import is_valid_stripe_subscription_id

        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
        if not is_valid_stripe_subscription_id(sub_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(sub_id)
        if (sub.get("status") or "").strip().lower() == "canceled":
            return jsonify({"ok": True, "message": "Subscription is already cancelled."}), 200

        # Immediate cancellation (no end-of-period scheduling).
        stripe.Subscription.delete(sub_id)
        # Stop pre-pack reminders for this order.
        order_service.update(order_id, {"reminder_opt_out": True})
        return jsonify({"ok": True, "message": "Subscription cancelled immediately."}), 200
    except stripe.error.InvalidRequestError as e:
        msg = str(e).lower()
        if "no such" in msg or "deleted" in msg or "canceled" in msg or "cancel" in msg:
            return jsonify({"ok": False, "error": "This subscription is no longer active."}), 400
        return jsonify({"ok": False, "error": (str(e) or "Could not cancel")[:200]}), 400
    except stripe.error.StripeError as e:
        return jsonify({"ok": False, "error": (str(e) or "Stripe error")[:200]}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@captions_bp.route("/captions/reminder-preference", methods=["PATCH"])
def captions_reminder_preference():
    """
    Update reminder opt-out for a caption subscription order.
    Requires login. Order must belong to customer and have stripe_subscription_id.
    Body: { "order_id": "...", "reminder_opt_out": true|false }
    """
    from api.auth_routes import get_current_customer
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        opt_out = data.get("reminder_opt_out")
        if not order_id:
            return jsonify({"ok": False, "error": "order_id required"}), 400
        if opt_out is None:
            return jsonify({"ok": False, "error": "reminder_opt_out required (true or false)"}), 400
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_id(order_id)
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403
        if not order.get("stripe_subscription_id"):
            return jsonify({"ok": False, "error": "Reminders only apply to subscription orders"}), 400
        if order_service.update(order_id, {"reminder_opt_out": bool(opt_out)}):
            return jsonify({"ok": True, "reminder_opt_out": bool(opt_out)}), 200
        return jsonify({"ok": False, "error": "Update failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


GET_PACK_SOONER_META_KEY = "lumo_get_pack_sooner"


@captions_bp.route("/captions/get-pack-sooner", methods=["POST"])
def captions_get_pack_sooner():
    """
    Reset subscription billing cycle to charge now and deliver pack.
    Requires login. Order must belong to customer, have active subscription, and not be paused.
    Uses Stripe Subscription.modify(billing_cycle_anchor='now', proration). If the invoice needs
    customer confirmation (3DS, new card), returns stripe_invoice_url for Stripe's hosted invoice page.
    Otherwise charges the saved card, clears the pack-sooner flag, and triggers generation here.
    Paid-via-hosted-invoice completions are handled by invoice.paid (subscription_update + metadata flag).
    """
    from api.auth_routes import get_current_customer
    from api.stripe_utils import is_valid_stripe_subscription_id

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        data = request.get_json() or {}
        order_id = (data.get("order_id") or "").strip()
        token = (data.get("token") or data.get("order_token") or "").strip()
        if not order_id and not token:
            return jsonify({"ok": False, "error": "order_id or token required"}), 400

        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        if token:
            order = order_service.get_by_token(token)
        else:
            order = order_service.get_by_id(order_id) if order_id else None
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order_id = order["id"]
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

        sub_id = (order.get("stripe_subscription_id") or "").strip()
        if not sub_id:
            return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
        if not is_valid_stripe_subscription_id(sub_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400

        if not order.get("intake"):
            return jsonify({"ok": False, "error": "Please complete your form first. Edit your form then try again."}), 400

        # Eligibility guard: allow only after at least one delivered pack exists
        # (either the subscription order itself or its upgraded-from one-off base order).
        delivered_self = bool(order.get("status") == "delivered" or order.get("delivered_at"))
        delivered_base = False
        upgraded_from = (order.get("upgraded_from_token") or "").strip()
        if upgraded_from:
            try:
                one_off = order_service.get_by_token(upgraded_from)
                delivered_base = bool(one_off and (one_off.get("status") == "delivered" or one_off.get("delivered_at")))
            except Exception:
                delivered_base = False
        if not (delivered_self or delivered_base):
            return jsonify({
                "ok": False,
                "error": "Get pack sooner is available after at least one pack has been delivered."
            }), 400

        # Check subscription is not paused
        pause_info = _get_subscription_pause_info(sub_id)
        if pause_info and pause_info.get("paused"):
            return jsonify({"ok": False, "error": "Your subscription is paused. Resume it first to get your pack sooner."}), 400

        import stripe

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub_cur = stripe.Subscription.retrieve(sub_id)
        meta = dict(sub_cur.get("metadata") or {})
        meta[GET_PACK_SOONER_META_KEY] = "1"
        try:
            sub = stripe.Subscription.modify(
                sub_id,
                billing_cycle_anchor="now",
                proration_behavior="create_prorations",
                payment_behavior="pending_if_incomplete",
                metadata=meta,
                expand=["latest_invoice"],
            )
        except stripe.error.InvalidRequestError as ire:
            # Older API configs may reject payment_behavior on update; fall back to legacy charge path.
            print(f"[get-pack-sooner] pending_if_incomplete not applied ({ire!r}); falling back")
            stripe.Subscription.modify(
                sub_id,
                billing_cycle_anchor="now",
                proration_behavior="create_prorations",
            )
            thread = threading.Thread(
                target=_run_generation_and_deliver,
                args=(order_id,),
                kwargs={"force_redeliver": True},
            )
            thread.daemon = False
            thread.start()
            return jsonify({
                "ok": True,
                "message": "Your pack will be generated and emailed to you within a few minutes.",
            }), 200

        inv = sub.get("latest_invoice")
        if isinstance(inv, str):
            inv = stripe.Invoice.retrieve(inv, expand=["payment_intent"])
        inv = inv if isinstance(inv, dict) else {}
        status = (inv.get("status") or "").strip()
        hosted = (inv.get("hosted_invoice_url") or "").strip()
        try:
            amount_due = int(inv.get("amount_due") or 0)
        except (TypeError, ValueError):
            amount_due = 0

        if status == "paid":
            try:
                stripe.Subscription.modify(sub_id, metadata={GET_PACK_SOONER_META_KEY: ""})
            except Exception as meta_err:
                print(f"[get-pack-sooner] could not clear metadata: {meta_err}")
            thread = threading.Thread(
                target=_run_generation_and_deliver,
                args=(order_id,),
                kwargs={"force_redeliver": True},
            )
            thread.daemon = False
            thread.start()
            payload = {
                "ok": True,
                "message": "Your pack will be generated and emailed to you within a few minutes.",
            }
            # When Stripe provides a hosted invoice URL, send the customer there so billing
            # (amount + period) is confirmed on Stripe even if the charge already succeeded.
            if hosted:
                payload["stripe_invoice_url"] = hosted
                payload["message"] = (
                    "Your payment went through. On the checkout page you can view your invoice and updated billing period. "
                    "Your pack will be emailed within a few minutes."
                )
            return jsonify(payload), 200

        if hosted and amount_due > 0 and status in ("open", "draft"):
            return jsonify({
                "ok": True,
                "stripe_invoice_url": hosted,
                "message": "Complete payment on the next screen to confirm. Your pack will be emailed within a few minutes after payment succeeds.",
            }), 200

        # No hosted URL but invoice still open — surface Stripe message if any
        if status in ("open", "draft") and hosted:
            return jsonify({
                "ok": True,
                "stripe_invoice_url": hosted,
                "message": "Confirm payment on checkout to finish.",
            }), 200

        thread = threading.Thread(
            target=_run_generation_and_deliver,
            args=(order_id,),
            kwargs={"force_redeliver": True},
        )
        thread.daemon = False
        thread.start()
        try:
            stripe.Subscription.modify(sub_id, metadata={GET_PACK_SOONER_META_KEY: ""})
        except Exception:
            pass
        return jsonify({
            "ok": True,
            "message": "Your pack will be generated and emailed to you within a few minutes.",
        }), 200
    except stripe.error.CardError as e:
        return jsonify({"ok": False, "error": e.user_message or "Your card was declined. Please try a different payment method."}), 400
    except stripe.error.StripeError as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@captions_bp.route("/captions/hide-pack", methods=["POST"])
def captions_hide_pack():
    """
    Remove a pack from account history (hidden from list). Requires login.
    Body: { "token": "..." }  (order intake token)
    """
    from api.auth_routes import get_current_customer

    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400
    try:
        data = request.get_json() or {}
        token = (data.get("token") or "").strip()
        if not token:
            return jsonify({"ok": False, "error": "token required"}), 400
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_token(token)
        if not order:
            return jsonify({"ok": False, "error": "Pack not found"}), 404
        order_email = (order.get("customer_email") or "").strip().lower()
        if order_email != email:
            return jsonify({"ok": False, "error": "This pack does not belong to your account"}), 403
        order_id = order.get("id")
        if not order_id:
            return jsonify({"ok": False, "error": "Invalid order"}), 400
        if order.get("status") != "delivered":
            return jsonify({"ok": False, "error": "Only delivered packs can be removed from history"}), 400
        if order_service.hide_from_history(order_id):
            return jsonify({"ok": True, "message": "Pack removed from history"}), 200
        return jsonify({"ok": False, "error": "Could not remove pack"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _run_scheduled_deliveries():
    """Process subscription orders whose scheduled_delivery_at is due (upgrade-from-one-off first pack)."""
    import threading
    from services.caption_order_service import CaptionOrderService
    order_service = CaptionOrderService()
    due = order_service.get_scheduled_delivery_orders_due()
    triggered = 0
    for order in due:
        order_id = order.get("id")
        if not order_id:
            continue
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = False
        thread.start()
        order_service.update(order_id, {"scheduled_delivery_at": None})
        triggered += 1
    return {"scheduled_deliveries_triggered": triggered}


def _run_stuck_first_deliveries(max_orders: int = 5) -> dict:
    """
    Pick orders that have intake but no captions_md and start generation threads.
    Called from daily cron and from APScheduler every 10 minutes in production.
    """
    import threading
    from services.caption_order_service import CaptionOrderService

    order_service = CaptionOrderService()
    stuck = order_service.get_orders_needing_first_delivery_recovery(limit=max_orders)
    triggered = 0
    for order in stuck:
        order_id = order.get("id")
        if not order_id:
            continue
        thread = threading.Thread(target=_run_generation_and_deliver, args=(str(order_id),))
        thread.daemon = False
        thread.start()
        triggered += 1
    salvage = order_service.get_orders_needing_captions_only_salvage(limit=max(1, min(3, max_orders)))
    salvage_triggered = 0
    for order in salvage:
        order_id = order.get("id")
        if not order_id:
            continue
        thread = threading.Thread(
            target=_run_generation_and_deliver,
            args=(str(order_id),),
            kwargs={"force_captions_only": True},
        )
        thread.daemon = False
        thread.start()
        salvage_triggered += 1
    if triggered:
        print(f"[Captions recovery] started delivery threads for {triggered} stuck order(s)")
    if salvage_triggered:
        print(f"[Captions recovery] started captions-only salvage for {salvage_triggered} failed order(s)")
    return {
        "stuck_first_delivery_triggered": triggered,
        "captions_only_salvage_triggered": salvage_triggered,
        "stuck_order_ids": [o.get("id") for o in stuck if o.get("id")],
        "salvage_order_ids": [o.get("id") for o in salvage if o.get("id")],
    }


@captions_bp.route("/captions-upgrade-reminder-unsubscribe", methods=["GET"])
def captions_upgrade_reminder_unsubscribe():
    """
    One-off upgrade reminder opt-out. Query: t=TOKEN (order token from the reminder email).
    Sets upgrade_reminder_opt_out on the order and shows a confirmation page.
    """
    token = (request.args.get("t") or "").strip()
    if not token:
        return _plain_page("Unsubscribe", "Missing link. Use the unsubscribe link from your upgrade reminder email."), 400
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        ok = order_service.set_upgrade_reminder_opt_out_by_token(token)
        if not ok:
            return _plain_page("Unsubscribe", "We couldn't find that link. You may have already unsubscribed."), 404
        return _plain_page(
            "Unsubscribed",
            "You're unsubscribed from upgrade reminders. We won't email you again about upgrading this one-off pack to a subscription.",
        ), 200
    except Exception as e:
        return _plain_page("Error", "Something went wrong. Please try again or contact us."), 500


def _plain_page(title: str, body: str, status: int = 200):
    """Return a simple HTML page with title and body."""
    from flask import Response
    import html as html_module
    safe_title = html_module.escape(title or "")
    safe_body = html_module.escape(body or "").replace("\n", "<br>")
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{safe_title} | Lumo 22</title></head><body style="font-family: sans-serif; max-width: 560px; margin: 4rem auto; padding: 1rem; line-height: 1.6;"><h1 style="font-size: 1.25rem;">{safe_title}</h1><p>{safe_body}</p><p><a href="/captions" style="color: #c9a227;">Back to 30 Days Captions</a></p></body></html>"""
    return Response(html, status=status, mimetype="text/html")


@captions_bp.route("/captions-send-reminders", methods=["GET"])
def captions_send_reminders():
    """
    Cron endpoint: send pre-pack reminder emails to subscription customers ~5 days before each period end.
    Also processes scheduled deliveries (upgrade-from-one-off first pack, 30 days after one-off).
    Protected by CRON_SECRET. Call daily from Railway cron (e.g. 0 9 * * * for 9am UTC).
    Query: ?secret=CRON_SECRET  or  Authorization: Bearer CRON_SECRET
    """
    secret = request.args.get("secret", "").strip() or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    if not getattr(Config, "CRON_SECRET", None) or secret != Config.CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from services.caption_reminder_service import run_reminders
        result = run_reminders()
        scheduled = _run_scheduled_deliveries()
        result["scheduled_deliveries_triggered"] = scheduled.get("scheduled_deliveries_triggered", 0)
        stuck = _run_stuck_first_deliveries(max_orders=5)
        result["stuck_first_delivery_triggered"] = stuck.get("stuck_first_delivery_triggered", 0)
        return jsonify({"ok": True, **result}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
