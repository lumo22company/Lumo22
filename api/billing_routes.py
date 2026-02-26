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
