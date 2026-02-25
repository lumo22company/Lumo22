"""
API routes for 30 Days Captions: checkout (redirect to intake after payment), intake submission, intake-link lookup.

Subscription (£79/mo) vs one-off (£97): same intake form and delivery flow; subscription uses Stripe
mode=subscription and is detected in webhook so we create order and send intake email on first payment.
"""
from flask import Blueprint, request, jsonify, redirect, Response
from config import Config

captions_bp = Blueprint("captions", __name__, url_prefix="/api")


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


# Amounts in smallest unit (pence/cents) for add-ons when using price_data (USD/EUR). GBP add-ons use existing Price IDs.
_CURRENCY_ADDON_AMOUNTS = {
    "gbp": {"extra_oneoff": 2900, "extra_sub": 1900, "stories_oneoff": 2900, "stories_sub": 1700},
    "usd": {"extra_oneoff": 3500, "extra_sub": 2400, "stories_oneoff": 3500, "stories_sub": 2100},
    "eur": {"extra_oneoff": 3200, "extra_sub": 2200, "stories_oneoff": 3200, "stories_sub": 1900},
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
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
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
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@captions_bp.route("/captions-checkout-subscription", methods=["GET"])
def captions_checkout_subscription():
    """
    Create a Stripe Checkout Session for Captions subscription.
    Query: ?platforms=N (1–4), ?selected=..., ?stories=1, ?currency=gbp|usd|eur.
    Extra platforms and Stories use add-on prices or price_data for USD/EUR.
    """
    import stripe
    currency = _parse_currency(request)
    price_id = _get_sub_price_id(currency)
    if not Config.STRIPE_SECRET_KEY or not price_id:
        return jsonify({"error": "Subscription not configured (STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID)"}), 503
    stripe.api_key = Config.STRIPE_SECRET_KEY
    platforms = _parse_platforms(request)
    selected = _parse_selected_platforms(request)
    stories = _parse_stories(request)
    extra_sub_id = (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    stories_sub_id = (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip()
    amounts = _CURRENCY_ADDON_AMOUNTS.get(currency, _CURRENCY_ADDON_AMOUNTS["gbp"])
    if platforms > 1 and currency == "gbp" and not extra_sub_id:
        return redirect(f"{request.host_url.rstrip('/')}/captions?error=extra_platform_not_configured", code=302)
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if base and not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    success_url = f"{base}/captions-thank-you?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/captions"
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
    metadata = {"product": "captions_subscription", "platforms": str(platforms), "include_stories": "1" if stories else "0"}
    if selected:
        metadata["selected_platforms"] = selected
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
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
    from datetime import datetime
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator, extract_day_categories_from_captions_md
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
        gen = CaptionGenerator()
        print(f"[Captions] Calling OpenAI for order {order_id}")
        captions_md = gen.generate(intake, previous_pack_themes=previous_pack_themes)
        from services.caption_pdf import build_caption_pdf, build_stories_pdf, get_logo_path
        logo_path = get_logo_path()
        try:
            pdf_bytes = build_caption_pdf(captions_md, logo_path=logo_path)
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
            stories_pdf = build_stories_pdf(captions_md, logo_path=logo_path)
            if stories_pdf:
                extra_attachments.append({
                    "filename": "30_Days_Story_Ideas.pdf",
                    "content": stories_pdf,
                    "mime_type": "application/pdf",
                })
        subject = "Your 30 Days of Social Media Captions"
        if extra_attachments:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. "
                "Both documents are attached.\n\nCopy each caption and story idea as you need them, or edit to fit. "
                "If you'd like any changes to tone or topics, reply to this email and we'll adjust.\n\nLumo 22\n"
            )
        else:
            body = (
                "Hi,\n\nYour 30 Days of Social Media Captions are ready. The document is attached.\n\n"
                "Copy each caption as you need it, or edit to fit. "
                "If you'd like any changes to tone or topics, reply to this email and we'll adjust.\n\nLumo 22\n"
            )
        notif = NotificationService()
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
        )
        if not ok:
            print(f"[Captions] Delivery email FAILED for order {order_id} to {customer_email}: {send_error}")
            order_service.set_failed(order_id)
            return (False, send_error or "Delivery email not sent")
        order_service.set_delivered(order_id, captions_md)
        # For subscriptions, record this pack's day categories so next month can vary
        if row.get("stripe_subscription_id"):
            day_categories = extract_day_categories_from_captions_md(captions_md)
            if day_categories and any(day_categories):
                month_str = datetime.utcnow().strftime("%Y-%m")
                order_service.append_pack_history(order_id, month_str, day_categories)
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
    Start caption generation + delivery in the background (same as after intake).
    Returns immediately so the request does not time out (502). Generation runs in a thread.
    Options:
      ?t=TOKEN   — copy the full token from your intake link (address bar: .../captions-intake?t=XXX)
      ?session_id=cs_xxx — or use the session_id from the thank-you page URL after payment
    Returns JSON: {"ok": true, "message": "..."} or {"ok": false, "error": "..."}.
    """
    import threading
    token = (request.args.get("t") or request.args.get("token") or "").strip()
    session_id = (request.args.get("session_id") or "").strip()
    if not token and not session_id:
        return jsonify({
            "ok": False,
            "error": "Missing ?t=TOKEN or ?session_id=cs_xxx. Use the token from your intake link (the part after t= in the address bar), or the session_id from the thank-you page URL.",
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
                "error": "Order not found. Use the full token from your intake link (address bar: .../captions-intake?t=XXX), or try ?session_id= with the session_id from the thank-you page URL.",
            }), 200
        order_id = order["id"]
        if not order.get("intake"):
            return jsonify({"ok": False, "error": "Please submit the form first."}), 200
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = True
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
    from services.caption_order_service import CaptionOrderService
    import threading

    data = request.get_json() or request.form
    if not data:
        return jsonify({"error": "Please fill in the form."}), 400

    token = (data.get("token") or data.get("t") or "").strip()
    if not token:
        return jsonify({"error": "Missing token. Use the link from your order email."}), 400

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
        "caption_examples": (data.get("caption_examples") or "").strip(),
        "caption_language": (data.get("caption_language") or "English (UK)").strip(),
        "include_stories": bool(data.get("include_stories")) or bool(order.get("include_stories")),
        "align_stories_to_captions": align_flag,
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
    platforms_count = max(1, int(order.get("platforms_count", 1)))

    if status == "awaiting_intake":
        platform_val = (intake.get("platform") or "").strip()
        if platform_val and "," in platform_val:
            platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
            if len(platform_parts) > platforms_count:
                return jsonify({
                    "error": f"You selected {len(platform_parts)} platforms but your order includes {platforms_count}. Please select no more than {platforms_count}."
                }), 400
        if not order_service.save_intake(order_id, intake):
            return jsonify({"error": "Failed to save. Please try again."}), 500
        thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
        thread.daemon = True
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
        if platform_val and "," in platform_val:
            platform_parts = [p.strip() for p in platform_val.split(",") if p.strip()]
            if len(platform_parts) > platforms_count:
                return jsonify({
                    "error": f"You selected {len(platform_parts)} platforms but your order includes {platforms_count}. Please select no more than {platforms_count}."
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
            "message": "Your form has been updated. (Note: This won't change captions already delivered.)",
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

    if download_type == "stories":
        if not order.get("include_stories"):
            return jsonify({"error": "This order did not include the Stories add-on"}), 400
        try:
            from services.caption_pdf import build_stories_pdf, get_logo_path
            logo_path = get_logo_path()
            pdf_bytes = build_stories_pdf(captions_md, logo_path=logo_path)
        except Exception as e:
            return jsonify({"error": "Could not build Stories PDF: {}".format(str(e))}), 500
        if not pdf_bytes:
            return jsonify({"error": "Stories PDF not available for this pack"}), 404
        filename = f"30_Days_Story_Ideas_{date_str}.pdf"
        disp = "inline" if inline else "attachment"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "{}; filename={}".format(disp, filename)},
        )

    # Captions PDF (default)
    try:
        from services.caption_pdf import build_caption_pdf, get_logo_path
        logo_path = get_logo_path()
        pdf_bytes = build_caption_pdf(captions_md, logo_path=logo_path)
    except Exception as e:
        return jsonify({"error": "Could not build PDF: {}".format(str(e))}), 500
    filename = f"30_Days_Captions_{date_str}.pdf"
    disp = "inline" if inline else "attachment"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "{}; filename={}".format(disp, filename)},
    )


def _get_subscription_pause_info(stripe_subscription_id: str):
    """Fetch subscription from Stripe; return {paused: bool, resumes_at: str or None}."""
    if not stripe_subscription_id or not Config.STRIPE_SECRET_KEY:
        return None
    try:
        import stripe
        from datetime import datetime
        stripe.api_key = Config.STRIPE_SECRET_KEY
        sub = stripe.Subscription.retrieve(stripe_subscription_id.strip())
        pc = sub.get("pause_collection")
        if not pc or not isinstance(pc, dict):
            return {"paused": False, "resumes_at": None}
        resumes_ts = pc.get("resumes_at")
        if not resumes_ts:
            return {"paused": True, "resumes_at": None}
        try:
            dt = datetime.utcfromtimestamp(resumes_ts)
            return {"paused": True, "resumes_at": dt.strftime("%d %b %Y")}
        except (TypeError, ValueError, OSError):
            return {"paused": True, "resumes_at": None}
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


@captions_bp.route("/captions-send-reminders", methods=["GET"])
def captions_send_reminders():
    """
    Cron endpoint: send pre-pack reminder emails to subscription customers ~5 days before each period end.
    Protected by CRON_SECRET. Call daily from Railway cron (e.g. 0 9 * * * for 9am UTC).
    Query: ?secret=CRON_SECRET  or  Authorization: Bearer CRON_SECRET
    """
    secret = request.args.get("secret", "").strip() or (request.headers.get("Authorization") or "").replace("Bearer ", "").strip()
    if not getattr(Config, "CRON_SECRET", None) or secret != Config.CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from services.caption_reminder_service import run_reminders
        result = run_reminders()
        return jsonify({"ok": True, **result}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
