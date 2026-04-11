"""
Billing portal: redirect customers to Stripe's hosted billing portal.
Requires customer login and a stripe_customer_id from a caption subscription.
"""
from typing import Optional

from flask import Blueprint, request, jsonify, redirect, url_for
from config import Config
from api.auth_routes import get_current_customer


# Display prices for plan-change emails (subscription base + extra platform + stories)
_DISPLAY_PRICES = {
    "gbp": {"symbol": "£", "sub": 79, "extra_sub": 19, "stories_sub": 17},
    "usd": {"symbol": "$", "sub": 99, "extra_sub": 24, "stories_sub": 21},
    "eur": {"symbol": "€", "sub": 89, "extra_sub": 22, "stories_sub": 19},
}


def _account_url():
    base = (Config.BASE_URL or request.url_root or "https://www.lumo22.com").strip().rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    return base.rstrip("/") + "/account"


def _subscription_monthly_price(currency: str, platforms: int, include_stories: bool) -> tuple[str, int]:
    """Return (symbol, amount) for subscription monthly price, e.g. ('£', 96)."""
    prices = _DISPLAY_PRICES.get((currency or "gbp").strip().lower(), _DISPLAY_PRICES["gbp"])
    amount = prices["sub"] + max(0, platforms - 1) * prices["extra_sub"]
    if include_stories:
        amount += prices["stories_sub"]
    return (prices["symbol"], amount)


def _normalize_platform_list(raw: str) -> list[str]:
    """Normalize comma-separated platform labels into supported unique values."""
    allowed = ["Instagram & Facebook", "LinkedIn", "TikTok", "Pinterest"]
    seen = set()
    out = []
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    for p in parts:
        if p in ("Instagram", "Facebook"):
            p = "Instagram & Facebook"
        if p in allowed and p not in seen:
            seen.add(p)
            out.append(p)
    return out


ALLOWED_PLATFORMS = frozenset(
    {"Instagram & Facebook", "LinkedIn", "TikTok", "Pinterest"}
)


def _parse_selected_platforms_from_body(raw_list) -> Optional[list]:
    """If client sends selected_platforms list, return normalized unique allowed labels; else None."""
    if raw_list is None:
        return None
    if not isinstance(raw_list, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for x in raw_list:
        s = str(x).strip() if x is not None else ""
        if not s:
            continue
        if s in ("Instagram", "Facebook"):
            s = "Instagram & Facebook"
        if s not in ALLOWED_PLATFORMS or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out if out else None


def _canonical_platform_string_from_order(order: dict) -> str:
    """Stable string for comparing with new selection after plan change."""
    intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    raw = (order.get("selected_platforms") or intake.get("platform") or "").strip()
    pc = max(1, int(order.get("platforms_count", 1)))
    return _coerce_platform_selection(raw, pc)


def _platform_signature(s: str) -> tuple:
    """Sorted tuple of platform labels for order-independent comparison."""
    return tuple(sorted(_normalize_platform_list(s)))


def _coerce_platform_selection(raw: str, desired_count: int) -> str:
    """
    Ensure selected platforms string aligns with desired count (1-4).
    When count increases, append unused defaults in a stable order.
    """
    desired = max(1, min(4, int(desired_count or 1)))
    defaults = ["Instagram & Facebook", "LinkedIn", "TikTok", "Pinterest"]
    items = _normalize_platform_list(raw)
    if not items:
        items = ["Instagram & Facebook"]
    # Fill up when moving to a higher platform count.
    for p in defaults:
        if len(items) >= desired:
            break
        if p not in items:
            items.append(p)
    # Trim if count reduced.
    items = items[:desired]
    return ", ".join(items)


def _stripe_subscription_item_updates_for_plan(
    items_data: list,
    new_platforms: int,
    new_stories: bool,
    stories_price_id: str,
    extra_platform_price_id: str,
) -> list:
    """
    Build the `items` array for stripe.Subscription.modify when changing plan.
    Updates existing base / extra / stories lines; **appends** `{price, quantity}` for add-ons
    that are not yet on the subscription (base-only checkouts never got extra/stories lines).
    Without this, DB and PDFs can show multi-platform + stories while Stripe stays on base price only.
    """
    item_updates: list = []
    had_extra_line = False
    had_stories_line = False
    for item in items_data:
        if not isinstance(item, dict):
            continue
        si_id = item.get("id")
        if not si_id:
            continue
        price = item.get("price")
        price_id = (price.get("id") if isinstance(price, dict) else None) or (
            price if isinstance(price, str) else None
        )
        qty = int(item.get("quantity", 1) or 1)

        if stories_price_id and price_id == stories_price_id:
            had_stories_line = True
            if not new_stories:
                item_updates.append({"id": si_id, "deleted": True})
            else:
                item_updates.append({"id": si_id, "quantity": 1})
        elif extra_platform_price_id and price_id == extra_platform_price_id:
            had_extra_line = True
            new_qty = max(0, new_platforms - 1)
            if new_qty == 0:
                item_updates.append({"id": si_id, "deleted": True})
            else:
                item_updates.append({"id": si_id, "quantity": new_qty})
        else:
            item_updates.append({"id": si_id, "quantity": qty})

    if new_stories and stories_price_id and not had_stories_line:
        item_updates.append({"price": stories_price_id, "quantity": 1})
    need_extra_qty = max(0, new_platforms - 1)
    if need_extra_qty > 0 and extra_platform_price_id and not had_extra_line:
        item_updates.append({"price": extra_platform_price_id, "quantity": need_extra_qty})

    return item_updates


def subscription_platforms_and_stories_from_stripe(sub_obj: dict) -> tuple[int, bool]:
    """
    Parse a Stripe subscription object (from API or webhook event) into our plan shape.
    Returns (platforms_count, include_stories). Used for plan-change emails from webhook.
    """
    base_ids = set()
    for key in (
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID",
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD",
        "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR",
    ):
        pid = (getattr(Config, key, None) or "").strip()
        if pid:
            base_ids.add(pid)
    extra_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    stories_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    items_raw = sub_obj.get("items")
    items = (items_raw.get("data") if isinstance(items_raw, dict) else []) if items_raw else []
    if not isinstance(items, list):
        items = []
    extra_qty = 0
    include_stories = False
    for item in items:
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        price_id = (price.get("id") if isinstance(price, dict) else None) or (price if isinstance(price, str) else None)
        if not price_id:
            continue
        qty = int(item.get("quantity", 1)) or 1
        if price_id in base_ids:
            pass
        elif price_id == extra_id:
            extra_qty += qty
        elif price_id == stories_id and qty > 0:
            include_stories = True
    platforms = 1 + extra_qty
    return (platforms, include_stories)


billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")

# Stripe Customer Portal: hosted_confirmation.custom_message max 500 characters (subscription_cancel deep link).
_PORTAL_CANCEL_CONFIRMATION_MESSAGE = (
    "Your captions subscription is cancelled—you won't be charged again. "
    "Delivered packs stay in your Lumo account under History. "
    "To download past invoices, choose Manage billing from your account and open Stripe's invoice list."
)


def _caption_orders_for_portal_customer():
    """Logged-in customer email → list of caption orders, or ([], None) on failure."""
    customer = get_current_customer()
    if not customer:
        return None, None, []
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return customer, email, []
    try:
        from services.caption_order_service import CaptionOrderService

        co_svc = CaptionOrderService()
        return customer, email, co_svc.get_by_customer_email(email)
    except Exception:
        return customer, email, []


@billing_bp.route("/portal", methods=["GET"])
def billing_portal():
    """
    Create Stripe billing portal session and redirect.
    Requires logged-in customer with a caption order that has stripe_customer_id.
    Optional ?order_token=xxx: open portal for that order's stripe_customer_id (helps when
    user has multiple billing accounts).
    """
    customer, email, orders = _caption_orders_for_portal_customer()
    if customer is None:
        return redirect(url_for("customer_login_page") + "?next=" + request.url)
    if not email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    order_token = (request.args.get("order_token") or "").strip()
    stripe_customer_id = None
    if order_token:
        for o in orders:
            if (o.get("token") or "").strip() == order_token:
                cid = (o.get("stripe_customer_id") or "").strip()
                if cid:
                    stripe_customer_id = cid
                    break
                break
    if not stripe_customer_id:
        for o in orders:
            cid = (o.get("stripe_customer_id") or "").strip()
            if cid:
                stripe_customer_id = cid
                break

    if not stripe_customer_id:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account?billing=no_sub", code=302)

    try:
        import stripe
        from config import Config
        if not Config.STRIPE_SECRET_KEY:
            return jsonify({"ok": False, "error": "Billing not configured"}), 503
        stripe.api_key = Config.STRIPE_SECRET_KEY

        base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
        if base and not base.startswith("http"):
            base = "https://" + base
        return_url = f"{base}/account" if base else "/account"

        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        url = session.get("url")
        if url:
            return redirect(url, code=302)
    except Exception:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account?billing=error", code=302)

    base = (request.url_root or "").strip().rstrip("/")
    return redirect(f"{base}/account?billing=error", code=302)


@billing_bp.route("/portal-cancel-subscription", methods=["GET"])
def billing_portal_cancel_subscription():
    """
    Deep-link into Stripe Customer Portal's subscription-cancel flow, then show a Lumo
    hosted_confirmation message (Stripe max 500 chars). Invoice history remains available
    via the normal Manage billing portal session.
    """
    customer, email, orders = _caption_orders_for_portal_customer()
    if customer is None:
        return redirect(url_for("customer_login_page") + "?next=" + request.url)
    if not email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    order_token = (request.args.get("order_token") or "").strip()
    if not order_token:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account/subscription?billing=no_token", code=302)

    order = None
    for o in orders:
        if (o.get("token") or "").strip() == order_token:
            order = o
            break
    if not order:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account/subscription?billing=not_found", code=302)

    order_email = (order.get("customer_email") or "").strip().lower()
    if order_email != email:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account/subscription?billing=forbidden", code=302)

    stripe_customer_id = (order.get("stripe_customer_id") or "").strip()
    subscription_id = (order.get("stripe_subscription_id") or "").strip()
    if not stripe_customer_id or not subscription_id:
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account/subscription?billing=no_sub", code=302)

    try:
        import stripe
        from api.stripe_utils import is_valid_stripe_subscription_id
        from config import Config

        if not Config.STRIPE_SECRET_KEY:
            return jsonify({"ok": False, "error": "Billing not configured"}), 503
        if not is_valid_stripe_subscription_id(subscription_id):
            base = (request.url_root or "").strip().rstrip("/")
            return redirect(f"{base}/account/subscription?billing=invalid_sub", code=302)
        stripe.api_key = Config.STRIPE_SECRET_KEY

        base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
        if base and not base.startswith("http"):
            base = "https://" + base
        return_url = f"{base}/account/subscription" if base else "/account/subscription"

        msg = _PORTAL_CANCEL_CONFIRMATION_MESSAGE.strip()
        if len(msg) > 500:
            msg = msg[:497] + "..."

        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
            flow_data={
                "type": "subscription_cancel",
                "subscription_cancel": {"subscription": subscription_id},
                "after_completion": {
                    "type": "hosted_confirmation",
                    "hosted_confirmation": {"custom_message": msg},
                },
            },
        )
        url = session.get("url")
        if url:
            return redirect(url, code=302)
    except Exception as e:
        print(f"[billing] portal-cancel-subscription: {e!r}")
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account/subscription?billing=cancel_flow_error", code=302)

    base = (request.url_root or "").strip().rstrip("/")
    return redirect(f"{base}/account/subscription?billing=error", code=302)


@billing_bp.route("/subscription-payment-method", methods=["POST"])
def set_subscription_payment_method():
    """
    Set which payment method (card) to use for a specific subscription.
    Body: { "subscription_id": "sub_xxx", "payment_method_id": "pm_xxx" }.
    Requires login; subscription must belong to the customer.
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    try:
        data = request.get_json() or {}
        subscription_id = (data.get("subscription_id") or "").strip()
        payment_method_id = (data.get("payment_method_id") or "").strip()
        if not subscription_id or not payment_method_id:
            return jsonify({"ok": False, "error": "subscription_id and payment_method_id required"}), 400
        from api.stripe_utils import is_valid_stripe_subscription_id
        if not is_valid_stripe_subscription_id(subscription_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400
    except Exception:
        return jsonify({"ok": False, "error": "Invalid request"}), 400

    try:
        from services.caption_order_service import CaptionOrderService
        from config import Config
        co_svc = CaptionOrderService()
        orders = co_svc.get_by_customer_email(email)
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not load orders"}), 500

    order_owns_sub = any(
        (o.get("stripe_subscription_id") or "").strip() == subscription_id
        for o in orders
    )
    if not order_owns_sub:
        return jsonify({"ok": False, "error": "This subscription does not belong to your account"}), 403

    if not getattr(Config, "STRIPE_SECRET_KEY", None):
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY
        stripe.Subscription.modify(
            subscription_id,
            default_payment_method=payment_method_id,
        )
        return jsonify({"ok": True, "message": "Payment method updated"}), 200
    except stripe.error.StripeError as e:
        return jsonify({"ok": False, "error": str(e) or "Stripe error"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@billing_bp.route("/add-stories-to-subscription", methods=["POST"])
def add_stories_to_subscription():
    """
    Add the Story Ideas add-on to the customer's existing caption subscription.
    Requires login; subscription must belong to the customer and not already include Stories.
    Stripe adds the Stories price to the subscription (billing follows Stripe’s rules for item changes).
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    try:
        data = request.get_json() or {}
        subscription_id = (data.get("subscription_id") or "").strip()
        from api.stripe_utils import is_valid_stripe_subscription_id
        if not subscription_id:
            return jsonify({"ok": False, "error": "subscription_id required"}), 400
        if not is_valid_stripe_subscription_id(subscription_id):
            return jsonify({"ok": False, "error": "Invalid subscription"}), 400
    except Exception:
        return jsonify({"ok": False, "error": "Invalid request"}), 400

    try:
        from services.caption_order_service import CaptionOrderService
        from config import Config
        co_svc = CaptionOrderService()
        orders = co_svc.get_by_customer_email(email)
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not load orders"}), 500

    order = None
    for o in orders:
        if (o.get("stripe_subscription_id") or "").strip() == subscription_id:
            order = o
            break
    if not order:
        return jsonify({"ok": False, "error": "This subscription does not belong to your account"}), 403
    if order.get("include_stories"):
        return jsonify({"ok": False, "error": "This subscription already includes Story Ideas"}), 400

    stories_price_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    if not stories_price_id:
        return jsonify({"ok": False, "error": "Stories add-on is not configured"}), 503

    if not getattr(Config, "STRIPE_SECRET_KEY", None):
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
        items_data = (sub.get("items") or {}).get("data") if hasattr(sub.get("items"), "get") else getattr(sub.get("items"), "data", None)
        items_data = items_data or []
        items = []
        for item in items_data:
            si_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            qty = item.get("quantity", 1) if isinstance(item, dict) else getattr(item, "quantity", 1)
            if si_id:
                items.append({"id": si_id, "quantity": int(qty) if qty else 1})
        if not items:
            return jsonify({"ok": False, "error": "Could not read subscription items"}), 500
        items.append({"price": stories_price_id, "quantity": 1})
        stripe.Subscription.modify(
            subscription_id,
            items=items,
            proration_behavior="create_prorations",
        )
        try:
            from app import invalidate_account_stripe_subscription_cache

            invalidate_account_stripe_subscription_cache(subscription_id)
        except Exception:
            pass
        co_svc.update(order["id"], {"include_stories": True})
        intake = order.get("intake") or {}
        if isinstance(intake, dict):
            intake = dict(intake)
            intake["include_stories"] = True
            co_svc.update_intake_only(order["id"], intake)
        customer_email = (order.get("customer_email") or "").strip()
        if customer_email and "@" in customer_email:
            try:
                from services.notifications import NotificationService
                notif = NotificationService()
                currency = (order.get("currency") or "gbp").strip().lower()
                platforms = max(1, int(order.get("platforms_count", 1)))
                old_sym, old_amt = _subscription_monthly_price(currency, platforms, False)
                new_sym, new_amt = _subscription_monthly_price(currency, platforms, True)
                notif.send_plan_change_confirmation_email(
                    customer_email,
                    change_summary="What changed: 30 Days Story Ideas has been added to your subscription.",
                    when_effective="Stories will be included in your next pack.",
                    account_url=_account_url(),
                    new_price_display=f"{new_sym}{new_amt}",
                    old_price_display=f"{old_sym}{old_amt}",
                    business_name=((order.get("intake") or {}).get("business_name") or None),
                )
            except Exception as e:
                print(f"[billing] Plan change confirmation email failed: {e}")
        return jsonify({
            "ok": True,
            "message": "Story Ideas added to your subscription. Stories will be included in your next pack.",
        }), 200
    except stripe.error.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e) or "Stripe error"
        return jsonify({"ok": False, "error": msg}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@billing_bp.route("/reduce-subscription", methods=["POST"])
def reduce_subscription():
    """
    Reduce subscription: fewer platforms and/or remove Story Ideas.
    Customer must accept new (lower) price. Modifies Stripe subscription and updates order.
    Body: { token, new_platforms (1–4), new_stories (bool) }.
    Requires login; order must belong to customer.
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    try:
        data = request.get_json() or {}
        token = (data.get("token") or "").strip()
        new_platforms = max(1, min(4, int(data.get("new_platforms") or 1)))
        new_stories = bool(data.get("new_stories"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid request"}), 400
    if not token:
        return jsonify({"ok": False, "error": "token required"}), 400

    try:
        from services.caption_order_service import CaptionOrderService
        from config import Config
        co_svc = CaptionOrderService()
        order = co_svc.get_by_token(token)
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not load order"}), 500
    if not order:
        return jsonify({"ok": False, "error": "Order not found"}), 404

    order_email = (order.get("customer_email") or "").strip().lower()
    customer_email = (customer.get("email") or "").strip().lower()
    if order_email != customer_email:
        return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

    subscription_id = (order.get("stripe_subscription_id") or "").strip()
    if not subscription_id:
        return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
    from api.stripe_utils import is_valid_stripe_subscription_id
    if not is_valid_stripe_subscription_id(subscription_id):
        return jsonify({"ok": False, "error": "Invalid subscription"}), 400

    order_platforms = max(1, int(order.get("platforms_count", 1)))
    order_has_stories = bool(order.get("include_stories"))
    if new_platforms >= order_platforms and (not order_has_stories or new_stories):
        return jsonify({"ok": False, "error": "No reduction in plan"}), 400

    stories_price_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    extra_platform_price_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    if not getattr(Config, "STRIPE_SECRET_KEY", None):
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    except stripe.error.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e) or "Stripe error"
        return jsonify({"ok": False, "error": msg}), 400

    items_data = (sub.get("items") or {}).get("data") if hasattr(sub.get("items"), "get") else getattr(sub.get("items"), "data", None)
    items_data = items_data or []
    item_updates = []
    for item in items_data:
        si_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        if not si_id:
            continue
        price = item.get("price") if isinstance(item, dict) else getattr(item, "price", None)
        price_id = price.get("id") if isinstance(price, dict) else getattr(price, "id", None) if price else None
        qty = item.get("quantity", 1) if isinstance(item, dict) else getattr(item, "quantity", 1)
        qty = int(qty) if qty else 1

        if price_id == stories_price_id:
            if not new_stories:
                item_updates.append({"id": si_id, "deleted": True})
            else:
                item_updates.append({"id": si_id, "quantity": 1})
        elif price_id == extra_platform_price_id:
            new_qty = max(0, new_platforms - 1)
            if new_qty == 0:
                item_updates.append({"id": si_id, "deleted": True})
            else:
                item_updates.append({"id": si_id, "quantity": new_qty})
        else:
            item_updates.append({"id": si_id, "quantity": qty})

    try:
        stripe.Subscription.modify(
            subscription_id,
            items=item_updates,
            proration_behavior="create_prorations",
        )
    except stripe.error.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e) or "Stripe error"
        return jsonify({"ok": False, "error": msg}), 400
    try:
        from app import invalidate_account_stripe_subscription_cache

        invalidate_account_stripe_subscription_cache(subscription_id)
    except Exception:
        pass

    selected_raw = (order.get("selected_platforms") or "").strip()
    intake_existing = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    intake_platform_raw = (intake_existing.get("platform") or "").strip() if intake_existing else ""
    selected_source = intake_platform_raw or selected_raw
    selected_synced = _coerce_platform_selection(selected_source, new_platforms)
    updates = {
        "platforms_count": new_platforms,
        "include_stories": new_stories,
        "selected_platforms": selected_synced,
    }
    updated_intake = dict(intake_existing or {})
    updated_intake["platform"] = selected_synced
    updated_intake["include_stories"] = new_stories
    updates["intake"] = updated_intake
    co_svc.update(order["id"], updates)

    customer_email = (order.get("customer_email") or "").strip()
    if customer_email and "@" in customer_email:
        try:
            from services.notifications import NotificationService
            notif = NotificationService()
            # Make the email explicit about what changed.
            # Examples:
            # - Reduced from 3 platforms to 1.
            # - Removed Story Ideas.
            # - Both.
            change_bits = []
            if new_platforms < order_platforms:
                change_bits.append(f"your subscription now includes {new_platforms} platform{'s' if new_platforms != 1 else ''} instead of {order_platforms}")
            if order_has_stories and not new_stories:
                change_bits.append("Story Ideas has been removed from your subscription")
            if not change_bits:
                change_text = "your plan has been updated."
            else:
                change_text = "; ".join(change_bits) + "."
            change_summary = f"What changed: {change_text}"
            when_effective = "Changes apply to your next pack. Packs already delivered will not change."
            currency = (order.get("currency") or "gbp").strip().lower()
            old_sym, old_amt = _subscription_monthly_price(currency, order_platforms, order_has_stories)
            new_sym, new_amt = _subscription_monthly_price(currency, new_platforms, new_stories)
            notif.send_plan_change_confirmation_email(
                customer_email,
                change_summary=change_summary,
                when_effective=when_effective,
                account_url=_account_url(),
                new_price_display=f"{new_sym}{new_amt}",
                old_price_display=f"{old_sym}{old_amt}",
                business_name=((order.get("intake") or {}).get("business_name") or None),
            )
        except Exception as e:
            print(f"[billing] Plan change confirmation email failed: {e}")

    return jsonify({
        "ok": True,
        "message": "Your plan has been updated. Your new (lower) price will be reflected on your next invoice. Changes apply to your next pack. Packs already delivered will not change.",
    }), 200


@billing_bp.route("/change-subscription-plan", methods=["POST"])
def change_subscription_plan():
    """
    Change subscription plan: platforms (count + which networks), Story Ideas, and alignment pref for intake.
    Body: {
      token, new_stories (bool),
      new_platforms (1–4) if selected_platforms omitted,
      selected_platforms (optional): list of 1–4 labels from
        Instagram & Facebook, LinkedIn, TikTok, Pinterest,
      align_stories_to_captions (optional bool; only when new_stories is true).
    - Stripe is updated only when platform count or Story Ideas billing changes.
    - Intake is always updated so the form can be prefilled.
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    try:
        data = request.get_json() or {}
        token = (data.get("token") or "").strip()
        new_stories = bool(data.get("new_stories"))
        selected_list = _parse_selected_platforms_from_body(data.get("selected_platforms"))
        align_stories_to_captions = bool(data.get("align_stories_to_captions")) if new_stories else False
        if selected_list is not None:
            if len(selected_list) < 1 or len(selected_list) > 4:
                return jsonify({"ok": False, "error": "Select 1–4 platforms"}), 400
            new_platforms = len(selected_list)
            selected_synced = ", ".join(selected_list)
        else:
            new_platforms = max(1, min(4, int(data.get("new_platforms") or 1)))
            selected_synced = None
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid request"}), 400
    if not token:
        return jsonify({"ok": False, "error": "token required"}), 400

    try:
        from services.caption_order_service import CaptionOrderService
        from config import Config
        co_svc = CaptionOrderService()
        order = co_svc.get_by_token(token)
    except Exception:
        return jsonify({"ok": False, "error": "Could not load order"}), 500
    if not order:
        return jsonify({"ok": False, "error": "Order not found"}), 404

    order_email = (order.get("customer_email") or "").strip().lower()
    customer_email = (customer.get("email") or "").strip().lower()
    if order_email != customer_email:
        return jsonify({"ok": False, "error": "This order does not belong to your account"}), 403

    subscription_id = (order.get("stripe_subscription_id") or "").strip()
    if not subscription_id:
        return jsonify({"ok": False, "error": "This order is not a subscription"}), 400
    from api.stripe_utils import is_valid_stripe_subscription_id
    if not is_valid_stripe_subscription_id(subscription_id):
        return jsonify({"ok": False, "error": "Invalid subscription"}), 400

    order_platforms = max(1, int(order.get("platforms_count", 1)))
    order_has_stories = bool(order.get("include_stories"))
    intake_existing = order.get("intake") if isinstance(order.get("intake"), dict) else {}
    old_align = bool(intake_existing.get("align_stories_to_captions"))

    if selected_synced is None:
        selected_raw = (order.get("selected_platforms") or "").strip()
        intake_platform_raw = (intake_existing.get("platform") or "").strip() if intake_existing else ""
        selected_source = intake_platform_raw or selected_raw
        selected_synced = _coerce_platform_selection(selected_source, new_platforms)

    canonical_existing = _canonical_platform_string_from_order(order)
    billing_changed = (new_platforms != order_platforms) or (new_stories != order_has_stories)
    meta_changed = (_platform_signature(selected_synced) != _platform_signature(canonical_existing)) or (
        align_stories_to_captions != old_align
    )

    if not billing_changed and not meta_changed:
        return jsonify({"ok": True, "no_op": True, "message": "Plan unchanged."}), 200

    stories_price_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    extra_platform_price_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    if not getattr(Config, "STRIPE_SECRET_KEY", None):
        return jsonify({"ok": False, "error": "Billing not configured"}), 503

    try:
        import stripe

        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
    except stripe.error.StripeError as e:
        msg = getattr(e, "user_message", None) or str(e) or "Stripe error"
        return jsonify({"ok": False, "error": msg}), 400

    must_sync_stripe = bool(billing_changed)
    if not must_sync_stripe:
        sp, ss = subscription_platforms_and_stories_from_stripe(sub)
        must_sync_stripe = (sp != new_platforms) or (ss != new_stories)

    if must_sync_stripe:
        items_data = (sub.get("items") or {}).get("data") if hasattr(sub.get("items"), "get") else getattr(sub.get("items"), "data", None)
        items_data = items_data or []
        item_updates = _stripe_subscription_item_updates_for_plan(
            items_data,
            new_platforms,
            new_stories,
            stories_price_id,
            extra_platform_price_id,
        )
        try:
            stripe.Subscription.modify(
                subscription_id,
                items=item_updates,
                proration_behavior="create_prorations",
            )
        except stripe.error.StripeError as e:
            msg = getattr(e, "user_message", None) or str(e) or "Stripe error"
            return jsonify({"ok": False, "error": msg}), 400
        try:
            from app import invalidate_account_stripe_subscription_cache

            invalidate_account_stripe_subscription_cache(subscription_id)
        except Exception:
            pass

    updates = {
        "platforms_count": new_platforms,
        "include_stories": new_stories,
        "selected_platforms": selected_synced,
    }
    updated_intake = dict(intake_existing or {})
    updated_intake["platform"] = selected_synced
    updated_intake["include_stories"] = new_stories
    updated_intake["align_stories_to_captions"] = align_stories_to_captions
    updates["intake"] = updated_intake
    co_svc.update(order["id"], updates)

    customer_email = (order.get("customer_email") or "").strip()
    if customer_email and "@" in customer_email:
        try:
            from services.notifications import NotificationService
            notif = NotificationService()
            change_bits = []
            if new_platforms != order_platforms:
                change_bits.append(
                    f"your subscription now includes {new_platforms} platform{'s' if new_platforms != 1 else ''} instead of {order_platforms}"
                )
            if _platform_signature(selected_synced) != _platform_signature(canonical_existing):
                change_bits.append(f"your platforms are now: {selected_synced}")
            if not order_has_stories and new_stories:
                change_bits.append("30 Days Story Ideas has been added to your subscription")
            elif order_has_stories and not new_stories:
                change_bits.append("Story Ideas has been removed from your subscription")
            if new_stories and align_stories_to_captions != old_align:
                if align_stories_to_captions:
                    change_bits.append("Story Ideas will align to each day's caption")
                else:
                    change_bits.append("Story Ideas will not be aligned to each day's caption")
            if not change_bits:
                change_text = "your plan has been updated."
            else:
                change_text = "; ".join(change_bits) + "."
            change_summary = f"What changed: {change_text}"
            when_effective = "Changes apply to your next pack. Packs already delivered will not change."
            currency = (order.get("currency") or "gbp").strip().lower()
            old_sym, old_amt = _subscription_monthly_price(currency, order_platforms, order_has_stories)
            new_sym, new_amt = _subscription_monthly_price(currency, new_platforms, new_stories)
            notif.send_plan_change_confirmation_email(
                customer_email,
                change_summary=change_summary,
                when_effective=when_effective,
                account_url=_account_url(),
                new_price_display=f"{new_sym}{new_amt}",
                old_price_display=f"{old_sym}{old_amt}",
                business_name=((order.get("intake") or {}).get("business_name") or None),
            )
        except Exception as e:
            print(f"[billing] Plan change confirmation email failed: {e}")

    return jsonify({
        "ok": True,
        "message": "Your plan has been updated. Changes apply to your next pack. Packs already delivered will not change.",
    }), 200
