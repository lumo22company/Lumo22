"""
Billing portal: redirect customers to Stripe's hosted billing portal.
Requires customer login and a stripe_customer_id from a caption subscription.
"""
from flask import Blueprint, request, jsonify, redirect, url_for
from api.auth_routes import get_current_customer

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")


@billing_bp.route("/portal", methods=["GET"])
def billing_portal():
    """
    Create Stripe billing portal session and redirect.
    Requires logged-in customer with a caption order that has stripe_customer_id.
    """
    customer = get_current_customer()
    if not customer:
        return redirect(url_for("customer_login_page") + "?next=" + request.url)

    email = (customer.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid customer"}), 400

    try:
        from services.caption_order_service import CaptionOrderService
        co_svc = CaptionOrderService()
        orders = co_svc.get_by_customer_email(email)
    except Exception as e:
        return jsonify({"ok": False, "error": "Could not load orders"}), 500

    stripe_customer_id = None
    for o in orders:
        cid = (o.get("stripe_customer_id") or "").strip()
        if cid:
            stripe_customer_id = cid
            break

    if not stripe_customer_id:
        from flask import url_for
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
    except Exception as e:
        from flask import url_for
        base = (request.url_root or "").strip().rstrip("/")
        return redirect(f"{base}/account?billing=error", code=302)

    base = (request.url_root or "").strip().rstrip("/")
    return redirect(f"{base}/account?billing=error", code=302)


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
    Stripe will prorate and add the Stories price to the subscription.
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
        if not subscription_id:
            return jsonify({"ok": False, "error": "subscription_id required"}), 400
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
        co_svc.update(order["id"], {"include_stories": True})
        intake = order.get("intake") or {}
        if isinstance(intake, dict):
            intake = dict(intake)
            intake["include_stories"] = True
            co_svc.update_intake_only(order["id"], intake)
        return jsonify({
            "ok": True,
            "message": "Story Ideas added to your subscription. You'll be charged a prorated amount; Stories will be included in your next pack.",
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
    """
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

    subscription_id = (order.get("stripe_subscription_id") or "").strip()
    if not subscription_id:
        return jsonify({"ok": False, "error": "This order is not a subscription"}), 400

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

    co_svc.update(order["id"], {"platforms_count": new_platforms, "include_stories": new_stories})

    return jsonify({
        "ok": True,
        "message": f"Your plan has been updated. Your new price will be reflected on your next invoice. Changes apply to your next pack.",
    }), 200
