"""
API routes for 30 Days Captions: checkout (redirect to intake after payment), intake submission, intake-link lookup.

Subscription (£79/mo) vs one-off (£97): same intake form and delivery flow; subscription uses Stripe
mode=subscription and is detected in webhook so we create order and send intake email on first payment.
"""
import os
import time
from flask import Blueprint, request, jsonify, redirect, Response, url_for
from urllib.parse import quote
from config import Config

captions_bp = Blueprint("captions", __name__, url_prefix="/api")

# Cooldown for intake email resends (order_id -> last_sent_timestamp) to avoid spam
_intake_email_sent_at = {}


def _get_referral_coupon_id():
    """
    If the customer is referred (ref= in query and valid, or logged-in with referred_by_customer_id),
    return the configured Stripe referral coupon ID; else None.
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


def _customer_has_blocking_captions_subscription(email: str) -> bool:
    """
    True if this customer already has an active/trialing/past_due Captions subscription in Stripe.
    Each completed subscription checkout creates a new Stripe subscription + caption_orders row;
    this guard prevents accidental duplicate monthly subscriptions for the same account.
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
            return True
    return False


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
    stories = _parse_stories(request)
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
    metadata = {"product": "captions", "platforms": str(platforms), "include_stories": "1" if stories else "0"}
    if selected:
        metadata["selected_platforms"] = selected
    referral_coupon = _get_referral_coupon_id()
    create_params = {
        "mode": "payment",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata,
    }
    if referral_coupon:
        create_params["discounts"] = [{"coupon": referral_coupon}]
    try:
        session = stripe.checkout.Session.create(**create_params)
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-checkout-subscription", methods=["GET"])
def captions_checkout_subscription():
    """
    Create a Stripe Checkout Session for Captions subscription.
    Query: ?platforms=N (1–4), ?selected=..., ?stories=1, ?currency=gbp|usd|eur, ?get_pack_now=1 (upgrade only).
    When get_pack_now=1 and copy_from=TOKEN: one-time payment for first month + immediate pack; subscription created with trial so next pack in 30 days.
    """
    from api.auth_routes import get_current_customer
    copy_from = (request.args.get("copy_from") or "").strip()
    get_pack_now = request.args.get("get_pack_now", "").strip().lower() in ("1", "true", "yes", "on")
    one_off = None
    customer = get_current_customer()
    if not customer:
        from urllib.parse import quote
        next_url = request.url
        signup_url = url_for("customer_signup_page") + "?next=" + quote(next_url, safe="")
        if copy_from:
            try:
                from services.caption_order_service import CaptionOrderService
                order = CaptionOrderService().get_by_token(copy_from)
                if order and (order.get("customer_email") or "").strip():
                    signup_url += "&email=" + quote((order.get("customer_email") or "").strip(), safe="")
            except Exception:
                pass
        return redirect(signup_url)
    import stripe
    currency = _parse_currency(request)
    price_id = _get_sub_price_id(currency)
    if not Config.STRIPE_SECRET_KEY or not price_id:
        return jsonify({"error": "Subscription not configured (STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    # Prevent multiple active Captions subscriptions for the same account (each checkout = new Stripe sub + new order row).
    if customer and (customer.get("email") or "").strip():
        try:
            if _customer_has_blocking_captions_subscription((customer.get("email") or "").strip().lower()):
                return redirect(url_for("account_page") + "?subscription_duplicate=1")
        except Exception as e:
            print(f"[captions_checkout_subscription] duplicate guard failed (non-fatal): {e}")
    platforms = _parse_platforms(request)
    selected = _parse_selected_platforms(request)
    stories = _parse_stories(request)
    base = _base_url_for_redirect()
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
    metadata = {"product": "captions_subscription", "platforms": str(platforms), "include_stories": "1" if stories else "0"}
    if selected:
        metadata["selected_platforms"] = selected
    if copy_from:
        metadata["copy_from"] = copy_from
        try:
            from services.caption_order_service import CaptionOrderService
            one_off = CaptionOrderService().get_by_token(copy_from)
        except Exception:
            one_off = None
        if not one_off:
            return jsonify({"error": "Base one-off order not found for this upgrade."}), 400
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
    referral_coupon = _get_referral_coupon_id()
    create_params = {
        "mode": "subscription",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": metadata,
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
    if referral_coupon:
        create_params["discounts"] = [{"coupon": referral_coupon}]
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


def _send_intake_email_for_order(order: dict) -> None:
    """Send receipt email then intake or subscription-welcome email (used by webhook and by API fallback)."""
    customer_email = (order.get("customer_email") or "").strip()
    if not customer_email or "@" not in customer_email:
        return
    intake_url = _build_intake_url(order)
    if not intake_url:
        return
    upgraded_from_oneoff = bool((order.get("upgraded_from_token") or "").strip())
    try:
        from services.notifications import NotificationService
        notif = NotificationService()
        if upgraded_from_oneoff:
            # Upgrade-from-one-off: prefilled form already exists, so we must not send the standard receipt copy
            # that says "complete your short intake form".
            ok = notif.send_subscription_welcome_prefilled_email(customer_email, intake_url)
            if ok:
                print(f"[captions-intake-link] Sent subscription welcome (prefilled) email to {customer_email}")
            else:
                print(f"[captions-intake-link] Subscription welcome email NOT sent to {customer_email}")
        else:
            try:
                notif.send_order_receipt_email(customer_email, order=order)
                time.sleep(2)  # Ensure confirmation is queued before intake so it arrives first
            except Exception as e:
                print(f"[captions-intake-link] Receipt email failed (non-fatal): {e!r}")
            ok = notif.send_intake_link_email(customer_email, intake_url, order)
            if ok:
                print(f"[captions-intake-link] Sent intake email to {customer_email}")
            else:
                print(f"[captions-intake-link] Intake email NOT sent (send_email returned False) to {customer_email}")
    except Exception as e:
        print(f"[captions-intake-link] Failed to send email: {e!r}")


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
    print(f"[captions-intake-link] Returning intake_url for session_id={session_id[:20]}...")
    return jsonify({
        "status": "ok",
        "intake_url": intake_url,
        "customer_email": customer_email or None,
        "is_subscription": is_subscription,
        "is_prefilled_from_oneoff": is_prefilled_from_oneoff,
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
    if (order.get("status") or "").strip().lower() == "awaiting_intake":
        order_id = order.get("id")
        if order_id:
            import time
            now = time.time()
            last = _intake_email_sent_at.get(str(order_id), 0)
            if now - last >= 300:
                _send_intake_email_for_order(order)
                _intake_email_sent_at[str(order_id)] = now
    is_subscription = bool((order.get("stripe_subscription_id") or "").strip())
    is_prefilled_from_oneoff = bool((order.get("upgraded_from_token") or "").strip())
    return jsonify({
        "status": "ok",
        "intake_url": intake_url,
        "customer_email": email,
        "is_subscription": is_subscription,
        "is_prefilled_from_oneoff": is_prefilled_from_oneoff,
    }), 200


def _run_generation_and_deliver(order_id: str, *, force_redeliver: bool = False):
    """Background: generate captions, save, email client. Runs outside request context.
    force_redeliver: when True, regenerate and email even if status is 'delivered' (used by force-deliver endpoint)."""
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
        print(f"[Captions] Order {order_id} already generating, skipping duplicate")
        return (True, None)
    intake = row.get("intake") or {}
    customer_email = (row.get("customer_email") or "").strip()
    if not customer_email:
        print(f"[Captions] No customer_email for order {order_id}, skipping")
        order_service.set_failed(order_id)
        return (False, "No customer_email for order")

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
        captions_md = gen.generate(intake, previous_pack_themes=previous_pack_themes, pack_start_date=pack_start_date)
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
        subject = "Your 30 Days of Social Media Captions"
        has_sub = bool(row.get("stripe_subscription_id"))
        base = (Config.BASE_URL or "").strip().rstrip("/")
        if not base.startswith("http"):
            base = "https://www.lumo22.com"
        backup_captions_url = f"{base}/captions-download?t={token}&type=captions"
        backup_stories_url = f"{base}/captions-download?t={token}&type=stories" if extra_attachments else None
        if extra_attachments:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. "
                "Both documents are attached.\n\nCopy each caption and story idea as you need them, or edit to fit.\n\n"
            )
        else:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions are ready. The document is attached.\n\n"
                "Copy each caption as you need it, or edit to fit.\n\n"
            )
        if has_sub:
            body += "Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account → Manage subscription.\n\n"
        body += "If attachments don't appear in your inbox, use your backup download link(s):\n"
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
        )
        # Save generated artifacts first so customer can still download even if email send fails.
        stories_pdf_bytes = extra_attachments[0]["content"] if extra_attachments else None
        order_service.set_delivered(
            order_id,
            captions_md,
            stories_pdf_bytes=stories_pdf_bytes,
            captions_pdf_bytes=file_content_bytes if mime_type == "application/pdf" else None,
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

    try:
        order_service = CaptionOrderService()
    except ValueError:
        return jsonify({"error": "Service unavailable"}), 503
    order = order_service.get_by_token(token)
    if not order:
        return jsonify({"error": "Invalid or expired link. Use the link from your order email."}), 404

    order_has_stories = bool(order.get("include_stories"))
    order_platforms_count = max(1, int(order.get("platforms_count", 1)))

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
        "voice_words": (data.get("voice_words") or "").strip(),
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
        "caption_language": (data.get("caption_language") or "English (UK)").strip(),
        "include_stories": order_has_stories and (bool(data.get("include_stories")) or bool((order.get("intake") or {}).get("include_stories"))),
        "align_stories_to_captions": align_flag,
    }

    form_wants_stories = bool(data.get("include_stories"))
    if form_wants_stories and not order_has_stories:
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
    subscription_id = (order.get("stripe_subscription_id") or "").strip()
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
        platform_val = (intake.get("platform") or "").strip()
        is_oneoff_edit = not (order.get("stripe_subscription_id") or "").strip()
        if platform_val and "," in platform_val:
            platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
            # One-off (delivered): allow saving more platforms so they can prepare form before upgrading
            if len(platform_parts) > order_platforms_count and not is_oneoff_edit:
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
        backup_captions_url = f"{base}/captions-download?t={safe_token}&type=captions"
        backup_stories_url = f"{base}/captions-download?t={safe_token}&type=stories" if include_stories else ""
        has_sub = bool(order.get("stripe_subscription_id"))

        if extra_attachments:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions and 30 Days of Story Ideas are attached.\n\n"
                "If attachments don't appear in your inbox, use your backup download link(s):\n"
                f"{backup_captions_url}\n{backup_stories_url}\n\n"
            )
        else:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions are attached.\n\n"
                "If attachments don't appear in your inbox, use your backup download link:\n"
                f"{backup_captions_url}\n\n"
            )
        if has_sub:
            body += "Deleting this email or the PDF does not cancel your subscription. To cancel, go to your account -> Manage subscription.\n\n"
        body += "Lumo 22\n"

        html_body = _captions_delivery_email_html(
            bool(extra_attachments),
            has_subscription=has_sub,
            backup_captions_url=backup_captions_url,
            backup_stories_url=backup_stories_url,
        )
        notif = NotificationService()
        ok, send_error = notif.send_email_with_attachment(
            email,
            "Your 30 Days of Social Media Captions",
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


def _get_subscription_pause_info(stripe_subscription_id: str):
    """Fetch subscription from Stripe; return {paused, resumes_at, cancel_at_period_end, ends_at}."""
    from api.stripe_utils import is_valid_stripe_subscription_id
    if not stripe_subscription_id or not Config.STRIPE_SECRET_KEY or not is_valid_stripe_subscription_id(stripe_subscription_id):
        return None
    try:
        import stripe
        from datetime import datetime
        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(stripe_subscription_id.strip())
        out = {"paused": False, "resumes_at": None, "cancel_at_period_end": False, "ends_at": None}
        # Pause info
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
        # Cancellation info (cancel at period end)
        if sub.get("cancel_at_period_end"):
            out["cancel_at_period_end"] = True
            cancel_ts = sub.get("cancel_at") or sub.get("current_period_end")
            if cancel_ts:
                try:
                    dt = datetime.utcfromtimestamp(cancel_ts)
                    out["ends_at"] = dt.strftime("%d %b %Y")
                except (TypeError, ValueError, OSError):
                    pass
        return out
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


@captions_bp.route("/captions/get-pack-sooner", methods=["POST"])
def captions_get_pack_sooner():
    """
    Reset subscription billing cycle to charge now and deliver pack immediately.
    Requires login. Order must belong to customer, have active subscription, and not be paused.
    Modifies Stripe subscription with billing_cycle_anchor='now', then triggers generation.
    """
    from api.auth_routes import get_current_customer
    from api.stripe_utils import is_valid_stripe_subscription_id
    import threading

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
        stripe.Subscription.modify(
            sub_id,
            billing_cycle_anchor="now",
            proration_behavior="create_prorations",
        )
        # Stripe creates and pays invoice. On success, trigger generation.
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = False
        thread.start()
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
    if triggered:
        print(f"[Captions recovery] started delivery threads for {triggered} stuck order(s)")
    return {
        "stuck_first_delivery_triggered": triggered,
        "stuck_order_ids": [o.get("id") for o in stuck if o.get("id")],
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
