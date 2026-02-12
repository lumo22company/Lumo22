"""
API routes for 30 Days Captions: checkout (redirect to intake after payment), intake submission, intake-link lookup.

Subscription (£79/mo) vs one-off (£97): same intake form and delivery flow; subscription uses Stripe
mode=subscription and is detected in webhook so we create order and send intake email on first payment.
"""
from flask import Blueprint, request, jsonify, redirect
from config import Config

captions_bp = Blueprint("captions", __name__, url_prefix="/api")


@captions_bp.route("/captions-checkout", methods=["GET"])
def captions_checkout():
    """
    Create a Stripe Checkout Session and redirect to it.
    After payment, Stripe redirects to /captions-thank-you?session_id=xxx so we can send the customer to the intake form.
    """
    import stripe
    if not Config.STRIPE_SECRET_KEY or not Config.STRIPE_CAPTIONS_PRICE_ID:
        # Fallback: redirect to payment link if set (old flow: thank-you → email link only)
        if Config.CAPTIONS_PAYMENT_LINK:
            return redirect(Config.CAPTIONS_PAYMENT_LINK)
        return jsonify({"error": "Checkout not configured (STRIPE_SECRET_KEY, STRIPE_CAPTIONS_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": Config.STRIPE_CAPTIONS_PRICE_ID, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"product": "captions"},
        )
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-checkout-subscription", methods=["GET"])
def captions_checkout_subscription():
    """
    Create a Stripe Checkout Session for Captions subscription (£79/month).
    Same success flow as one-off: redirect to thank-you then intake. Webhook handles first payment.
    """
    import stripe
    price_id = getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or ""
    price_id = (price_id or "").strip()
    if not Config.STRIPE_SECRET_KEY or not price_id:
        return jsonify({"error": "Subscription not configured (STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"product": "captions_subscription"},
        )
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-webhook-test", methods=["GET"])
def captions_webhook_test():
    """
    Run the same steps as the Stripe webhook handler (create order + send intake email).
    Open in browser to see the REAL error on Railway: https://lumo-22-production.up.railway.app/api/captions-webhook-test
    Returns JSON: {"ok": true} or {"ok": false, "error": "the actual error message"}.
    """
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


@captions_bp.route("/captions-intake-link", methods=["GET"])
def captions_intake_link():
    """
    Return the intake form URL for a Stripe checkout session (for thank-you page redirect).
    Used after payment: thank-you page has session_id and polls this until the webhook has created the order.
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
    if not order:
        return jsonify({"status": "pending"}), 200
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    token = order.get("token") or ""
    if not token:
        return jsonify({"status": "pending"}), 200
    intake_url = f"{base}/captions-intake?t={token}"
    return jsonify({"status": "ok", "intake_url": intake_url}), 200


def _run_generation_and_deliver(order_id: str):
    """Background: generate captions, save, email client. Runs outside request context."""
    import traceback
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator
    from services.notifications import NotificationService

    print(f"[Captions] Starting generation for order {order_id}")
    order_service = CaptionOrderService()
    row = order_service.get_by_id(order_id)
    if not row:
        print(f"[Captions] Order {order_id} not found, skipping")
        return (False, "Order not found")
    intake = row.get("intake") or {}
    customer_email = (row.get("customer_email") or "").strip()
    if not customer_email:
        print(f"[Captions] No customer_email for order {order_id}, skipping")
        order_service.set_failed(order_id)
        return (False, "No customer_email for order")

    order_service.set_generating(order_id)
    try:
        gen = CaptionGenerator()
        print(f"[Captions] Calling OpenAI for order {order_id}")
        captions_md = gen.generate(intake)
        order_service.set_delivered(order_id, captions_md)
        filename = "30_Days_Captions.md"
        subject = "Your 30 Days of Social Media Captions"
        body = """Hi,

Your 30 Days of Social Media Captions are ready. The document is attached.

Copy each caption as you need it, or edit to fit. If you’d like any changes to tone or topics, reply to this email and we’ll adjust.

Lumo 22
"""
        notif = NotificationService()
        print(f"[Captions] Sending delivery email to {customer_email} for order {order_id}")
        ok = notif.send_email_with_attachment(
            customer_email,
            subject,
            body,
            filename=filename,
            file_content=captions_md,
            mime_type="text/markdown",
        )
        if not ok:
            print(f"[Captions] Delivery email FAILED for order {order_id} to {customer_email}")
            return (False, "SendGrid returned False (delivery email not sent)")
        print(f"[Captions] Delivery email sent for order {order_id} to {customer_email}")
        return (True, None)
    except Exception as e:
        print(f"[Captions] Generation or delivery failed for order {order_id}: {e}")
        traceback.print_exc()
        order_service.set_failed(order_id)
        return (False, str(e))


@captions_bp.route("/captions-deliver-test", methods=["GET"])
def captions_deliver_test():
    """
    Run caption generation + delivery synchronously for an order (by token).
    Use to see the REAL error if the background job fails.
    Open: https://lumo-22-production.up.railway.app/api/captions-deliver-test?t=YOUR_TOKEN
    (Copy the token from your intake link: /captions-intake?t=TOKEN)
    Returns JSON: {"ok": true} or {"ok": false, "error": "the actual error message"}.
    """
    token = (request.args.get("t") or request.args.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Missing ?t=TOKEN (copy from your intake link)"}), 200
    try:
        from services.caption_order_service import CaptionOrderService
        order_service = CaptionOrderService()
        order = order_service.get_by_token(token)
        if not order:
            return jsonify({"ok": False, "error": "Order not found for this token"}), 200
        order_id = order["id"]
        if not order.get("intake"):
            return jsonify({"ok": False, "error": "Order has no intake yet — submit the intake form first"}), 200
        success, err = _run_generation_and_deliver(order_id)
        if success:
            return jsonify({"ok": True, "message": "Generation and delivery ran. Check your email (and spam)."}), 200
        err = (err or "Unknown error")[:500]
        err = "".join(c for c in err if ord(c) < 128)
        return jsonify({"ok": False, "error": err}), 200
    except Exception as e:
        err = (str(e) or repr(e))[:500]
        err = "".join(c for c in err if ord(c) < 128)
        return jsonify({"ok": False, "error": err or "Unknown error"}), 200


@captions_bp.route("/captions-intake", methods=["POST"])
def captions_intake_submit():
    """
    Submit intake for a 30 Days Captions order (identified by token).
    Saves intake and starts generation in background; returns immediately.
    """
    from services.caption_order_service import CaptionOrderService
    import threading

    data = request.get_json() or request.form
    if not data:
        return jsonify({"error": "Missing intake data"}), 400

    token = (data.get("token") or data.get("t") or "").strip()
    if not token:
        return jsonify({"error": "Missing token. Use the link from your order email."}), 400

    intake = {
        "business_type": (data.get("business_type") or "").strip(),
        "offer_one_line": (data.get("offer_one_line") or "").strip(),
        "audience": (data.get("audience") or "").strip(),
        "audience_cares": (data.get("audience_cares") or "").strip(),
        "voice_words": (data.get("voice_words") or "").strip(),
        "voice_avoid": (data.get("voice_avoid") or "").strip(),
        "platform": (data.get("platform") or "").strip(),
        "platform_habits": (data.get("platform_habits") or "").strip(),
        "goal": (data.get("goal") or "").strip(),
        "caption_examples": (data.get("caption_examples") or "").strip(),
    }

    try:
        order_service = CaptionOrderService()
    except ValueError as e:
        return jsonify({"error": "Service unavailable"}), 503

    order = order_service.get_by_token(token)
    if not order:
        return jsonify({"error": "Invalid or expired link. Use the link from your order email."}), 404

    order_id = order["id"]
    status = order.get("status") or ""

    if status == "awaiting_intake":
        if not order_service.save_intake(order_id, intake):
            return jsonify({"error": "Failed to save intake"}), 500
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = True
        thread.start()
        return jsonify({
            "success": True,
            "message": "Thanks. We're generating your 30 captions now. You'll receive them by email within a few minutes.",
            "customer_email": order.get("customer_email") or "",
        }), 200

    # Edit mode: order already has intake (intake_completed, generating, delivered)
    if order.get("intake") and status in ("intake_completed", "generating", "delivered"):
        if not order_service.update_intake_only(order_id, intake):
            return jsonify({"error": "Failed to update intake"}), 500
        return jsonify({
            "success": True,
            "message": "Your intake has been updated. (Note: This won't change captions already delivered.)",
            "customer_email": order.get("customer_email") or "",
        }), 200

    return jsonify({"error": "This order has already been completed or is in progress."}), 400
