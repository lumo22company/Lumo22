"""
Webhook handlers for third-party integrations.
Allows external services to send leads to the system.
"""
import re
from flask import Blueprint, request, jsonify, current_app
from config import Config
from api.routes import capture_lead

webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# --- Stripe (30 Days Captions) ---
CAPTIONS_AMOUNT_PENCE = 9700  # £97

def _sanitize_base_url(raw: str) -> str:
    """Remove non-printable ASCII (e.g. newline from env) so URLs are valid."""
    if not raw or not isinstance(raw, str):
        return ""
    # Strip and remove control chars so SendGrid/URL validators don't raise
    s = re.sub(r"[\x00-\x1f\x7f]", "", raw.strip())
    return s.rstrip("/").strip()


def _sanitize_for_email(text: str) -> str:
    """Remove control chars (except newline) so SendGrid/APIs don't raise 'Invalid non-printable ASCII'."""
    if not text or not isinstance(text, str):
        return ""
    # Keep \n (0x0a) for line breaks; remove \r and other control chars
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)


def _is_captions_subscription_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions subscription (£79/month). Reuses same intake/delivery as one-off."""
    mode = (session.get("mode") or "") if isinstance(session, dict) else ""
    if mode != "subscription":
        return False
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "captions_subscription":
        return True
    sub_price_ids = [
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
    ]
    sub_price_ids = [x for x in sub_price_ids if x]
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = (item.get("price") or {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
        if pid and pid in sub_price_ids:
            return True
    return False


def _is_captions_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions (one-off, any currency)."""
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "captions":
        return True
    amount_raw = session.get("amount_total")
    try:
        amount = int(amount_raw) if amount_raw is not None else 0
    except (TypeError, ValueError):
        amount = 0
    currency = (session.get("currency") or "gbp").strip().lower() if isinstance(session, dict) else "gbp"
    if currency == "gbp" and amount == CAPTIONS_AMOUNT_PENCE:
        return True
    # Match by price ID (GBP, USD, EUR)
    captions_price_ids = []
    for key in ("STRIPE_CAPTIONS_PRICE_ID", "STRIPE_CAPTIONS_PRICE_ID_USD", "STRIPE_CAPTIONS_PRICE_ID_EUR"):
        pid = (getattr(Config, key, None) or "").strip()
        if pid:
            captions_price_ids.append(pid)
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = item.get("price", {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
        if pid and pid in captions_price_ids:
            return True
    return False


def _get_customer_email_from_session(session):
    """Get customer email from Stripe Checkout Session. Never use session.customer (it's null for Checkout)."""
    # #4 Fix: Email is in customer_details.email, NOT customer_email (which is null for Checkout)
    details = session.get("customer_details") if hasattr(session, "get") else None
    if details is not None:
        # Handle both dict and StripeObject (Stripe SDK may give object, not dict)
        email = None
        if isinstance(details, dict):
            email = details.get("email") or details.get("customer_email")
        elif hasattr(details, "get"):
            email = details.get("email") or details.get("customer_email")
        else:
            email = getattr(details, "email", None) or getattr(details, "customer_email", None)
        if email and isinstance(email, str):
            return email.strip()
    # Top-level fallback (older payloads)
    email = session.get("customer_email") if hasattr(session, "get") else getattr(session, "customer_email", None)
    if email and isinstance(email, str):
        return email.strip()
    # If still missing, fetch the session from Stripe API
    try:
        import stripe
        sid = session.get("id") if hasattr(session, "get") else getattr(session, "id", None)
        if Config.STRIPE_SECRET_KEY and sid:
            stripe.api_key = Config.STRIPE_SECRET_KEY
            full = stripe.checkout.Session.retrieve(sid, expand=["customer_details"])
            details = full.get("customer_details") or {}
            if isinstance(details, dict):
                email = details.get("email") or details.get("customer_email")
            else:
                email = getattr(details, "email", None) or getattr(details, "customer_email", None)
            if email:
                return str(email).strip()
            email = full.get("customer_email")
            if email:
                return str(email).strip()
    except Exception as e:
        print(f"[Stripe webhook] Could not retrieve session for email: {e}")
    return None


def _handle_captions_payment(session):
    """Create caption order and send intake-link email. Used for both one-off (£97) and subscription (£79/mo) captions.
    Idempotent: if we already have an order for this session, resend email and return."""
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
    customer_email = _get_customer_email_from_session(session)
    if not customer_email:
        print("[Stripe webhook] No customer email in session; intake email not sent.")
        return
    print(f"[Stripe webhook] Customer email from session: {customer_email}")

    stripe_customer_id = (session.get("customer") or "").strip() or None
    stripe_subscription_id = (session.get("subscription") or "").strip() or None
    if stripe_customer_id:
        print(f"[Stripe webhook] Stripe customer: {stripe_customer_id[:20]}...")
    if stripe_subscription_id:
        print(f"[Stripe webhook] Stripe subscription: {stripe_subscription_id[:20]}...")

    meta = (session.get("metadata") or {}) if isinstance(session, dict) else getattr(session, "metadata", None) or {}
    if hasattr(meta, "get"):
        platforms_count = meta.get("platforms")
        selected_platforms = meta.get("selected_platforms")
        include_stories = meta.get("include_stories") in ("1", "true", "yes")
    else:
        platforms_count = getattr(meta, "platforms", None)
        selected_platforms = getattr(meta, "selected_platforms", None)
        include_stories = getattr(meta, "include_stories", None) in ("1", "true", "yes")
    try:
        platforms_count = max(1, int(platforms_count)) if platforms_count is not None else 1
    except (TypeError, ValueError):
        platforms_count = 1
    selected_platforms = (selected_platforms or "").strip() or None

    currency = (session.get("currency") or "gbp") if isinstance(session, dict) else getattr(session, "currency", None) or "gbp"
    currency = str(currency).strip().lower()
    if currency not in ("gbp", "usd", "eur"):
        currency = "gbp"

    order_service = CaptionOrderService()
    # Idempotent: if Stripe retries or API created first, we may already have an order
    existing = order_service.get_by_stripe_session_id(session_id) if session_id else None
    order_created_here = False
    if existing:
        print(f"[Stripe webhook] Order already exists for session {session_id[:20]}..., skipping emails (already sent)")
        order = existing
        if stripe_customer_id or stripe_subscription_id:
            updates = {}
            if stripe_customer_id and not existing.get("stripe_customer_id"):
                updates["stripe_customer_id"] = stripe_customer_id
            if stripe_subscription_id and not existing.get("stripe_subscription_id"):
                updates["stripe_subscription_id"] = stripe_subscription_id
            if updates:
                order_service.update(existing["id"], updates)
                order = {**existing, **updates}
    else:
        try:
            copy_from = (meta.get("copy_from") or "").strip() if isinstance(meta, dict) else getattr(meta, "copy_from", None) or ""
            copy_from = str(copy_from).strip() if copy_from else None
            order = order_service.create_order(
                customer_email=customer_email,
                stripe_session_id=session_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                platforms_count=platforms_count,
                selected_platforms=selected_platforms,
                include_stories=include_stories,
                currency=currency,
                upgraded_from_token=copy_from if stripe_subscription_id else None,
            )
        except Exception as e:
            print(f"[Stripe webhook] Failed to create order in Supabase: {e}")
            raise
        order_created_here = True
        print(f"[Stripe webhook] Order created id={order.get('id')} token=...{order['token'][-6:]}")
    token = order["token"]
    base = _sanitize_base_url(Config.BASE_URL or "")
    if not base or not base.startswith("http"):
        base = "https://lumo-22-production.up.railway.app"
    safe_token = str(token).strip()
    copy_from = (meta.get("copy_from") or "").strip() if isinstance(meta, dict) else getattr(meta, "copy_from", None) or ""
    copy_from = str(copy_from).strip() if copy_from else ""
    # copy_from was already used above when creating order (as upgraded_from_token)
    intake_url = f"{base}/captions-intake?t={safe_token}"
    if copy_from:
        intake_url += f"&copy_from={copy_from}"

    # Only send emails when we created the order; if existing, API or prior webhook already sent
    if order_created_here:
        notif = NotificationService()
        try:
            notif.send_order_receipt_email(customer_email, order=order, session=session)
        except Exception as receipt_err:
            print(f"[Stripe webhook] Receipt email failed (non-fatal): {receipt_err}")
        print(f"[Stripe webhook] Sending intake email to {customer_email}")
        ok = False
        try:
            ok = notif.send_intake_link_email(customer_email, intake_url, order)
        except Exception as send_err:
            # Retry with hardcoded URL so env/hidden chars or SendGrid validation can't cause 500
            print(f"[Stripe webhook] Send failed ({send_err}), retrying with hardcoded fallback URL")
            fallback_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={safe_token}"
            if copy_from:
                fallback_url += f"&copy_from={copy_from}"
            try:
                ok = notif.send_intake_link_email(customer_email, fallback_url, order)
            except Exception as fallback_err:
                print(f"[Stripe webhook] Fallback send also failed: {fallback_err}")
                raise
        if not ok:
            print(f"[Stripe webhook] intake-link email FAILED to send to {customer_email}")
        else:
            print(f"[Stripe webhook] intake-link email sent to {customer_email}")

    # Referrer reward: if the purchaser was referred (has account with referred_by_customer_id), give referrer one credit.
    try:
        from services.customer_auth_service import CustomerAuthService
        auth_svc = CustomerAuthService()
        buyer = auth_svc.get_by_email(customer_email)
        if buyer and buyer.get("referred_by_customer_id"):
            referrer_id = str(buyer["referred_by_customer_id"])
            if auth_svc.increment_referral_discount_credits(referrer_id):
                print(f"[Stripe webhook] Referrer reward: +1 credit for customer {referrer_id[:8]}... (referred friend paid)")
    except Exception as e:
        print(f"[Stripe webhook] Referrer credit increment failed (non-fatal): {e}")


@webhook_bp.route('/stripe', methods=['GET', 'POST'])
def stripe_webhook():
    """
    GET: Verify the webhook URL is reachable (open in browser).
    POST: Stripe webhook: checkout.session.completed for 30 Days Captions.
    """
    if request.method == 'GET':
        return jsonify({
            "message": "Stripe webhook endpoint. Stripe sends POST here.",
            "configured": bool(Config.STRIPE_WEBHOOK_SECRET),
        }), 200

    import stripe

    if not Config.STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Stripe webhook not configured"}), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.SignatureVerificationError as e:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event.get("type") if hasattr(event, "get") else getattr(event, "type", None)
    print(f"[Stripe webhook] Webhook received: event.type={event_type}")

    try:
        if event_type == "invoice.paid":
            invoice = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not invoice or not isinstance(invoice, dict):
                print("[Stripe webhook] invoice.paid: missing or invalid invoice; skipping.")
                return jsonify({"received": True}), 200
            billing_reason = (invoice.get("billing_reason") or "").strip()
            if billing_reason != "subscription_cycle":
                print(f"[Stripe webhook] invoice.paid: billing_reason={billing_reason}, not subscription_cycle; skipping.")
                return jsonify({"received": True}), 200
            sub_id = (invoice.get("subscription") or "").strip()
            if not sub_id:
                print("[Stripe webhook] invoice.paid: no subscription on invoice; skipping.")
                return jsonify({"received": True}), 200
            # Accept any captions subscription price (GBP, USD, EUR)
            valid_price_ids = [
                p for p in [
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
                ] if p
            ]
            if not valid_price_ids:
                return jsonify({"received": True}), 200
            is_captions = False
            lines_data = (invoice.get("lines") or {})
            if isinstance(lines_data, dict):
                lines_data = lines_data.get("data") or []
            if not isinstance(lines_data, list):
                lines_data = []
            for line in lines_data:
                price = line.get("price")
                if isinstance(price, dict):
                    pid = price.get("id")
                elif isinstance(price, str):
                    pid = price
                else:
                    pid = getattr(price, "id", None) if price else None
                if pid and pid in valid_price_ids:
                    is_captions = True
                    break
            if not is_captions:
                print("[Stripe webhook] invoice.paid: not captions subscription; skipping.")
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from api.captions_routes import _run_generation_and_deliver
            import threading
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                print(f"[Stripe webhook] invoice.paid: no order for subscription {sub_id[:20]}...; skipping.")
                return jsonify({"received": True}), 200
            if not order.get("intake"):
                print(f"[Stripe webhook] invoice.paid: order {order.get('id')} has no intake; skipping delivery.")
                return jsonify({"received": True}), 200
            order_id = order["id"]
            print(f"[Stripe webhook] invoice.paid: triggering generation for order {order_id} (subscription renewal)")
            thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
            thread.daemon = True
            thread.start()
            return jsonify({"received": True}), 200

        if event_type == "customer.subscription.deleted":
            # Subscription cancelled: send confirmation email (captions only)
            sub_obj = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not sub_obj or not isinstance(sub_obj, dict):
                return jsonify({"received": True}), 200
            sub_id = (sub_obj.get("id") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from services.notifications import NotificationService
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                return jsonify({"received": True}), 200
            customer_email = (order.get("customer_email") or "").strip()
            if customer_email and "@" in customer_email:
                base = _sanitize_base_url(Config.BASE_URL or "https://www.lumo22.com")
                if not base or not base.startswith("http"):
                    base = "https://www.lumo22.com"
                captions_url = base.rstrip("/") + "/captions"
                try:
                    notif = NotificationService()
                    notif.send_subscription_cancelled_email(customer_email, captions_url)
                    print(f"[Stripe webhook] Subscription cancelled confirmation sent to {customer_email}")
                except Exception as e:
                    print(f"[Stripe webhook] Subscription cancelled email failed: {e}")
            return jsonify({"received": True}), 200

        if event_type == "customer.subscription.updated":
            # Plan change via Stripe billing portal: send confirmation email
            sub_obj = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not sub_obj or not isinstance(sub_obj, dict):
                return jsonify({"received": True}), 200
            sub_id = (sub_obj.get("id") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from services.notifications import NotificationService
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                return jsonify({"received": True}), 200
            customer_email = (order.get("customer_email") or "").strip()
            if customer_email and "@" in customer_email:
                base = (Config.BASE_URL or "https://www.lumo22.com").strip().rstrip("/")
                if not base.startswith("http"):
                    base = "https://" + base
                account_url = base + "/account"
                try:
                    notif = NotificationService()
                    notif.send_plan_change_confirmation_email(
                        customer_email,
                        change_summary="Your subscription has been updated.",
                        when_effective="Changes will apply to your next pack. Your new price will be reflected on your next invoice.",
                        account_url=account_url,
                    )
                    print(f"[Stripe webhook] Plan change confirmation sent to {customer_email}")
                except Exception as e:
                    print(f"[Stripe webhook] Plan change confirmation email failed: {e}")
            return jsonify({"received": True}), 200

        if event_type == "invoice.created":
            # Apply referrer 10% discount to referrer's next billing period(s). One credit per referred friend; one credit consumed per invoice.
            invoice = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not invoice or not isinstance(invoice, dict):
                return jsonify({"received": True}), 200
            sub_id = (invoice.get("subscription") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            invoice_id = (invoice.get("id") or "").strip()
            if not invoice_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from services.customer_auth_service import CustomerAuthService
            from services.referral_reward_service import ReferralRewardService
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                return jsonify({"received": True}), 200
            customer_email = (order.get("customer_email") or "").strip()
            if not customer_email:
                return jsonify({"received": True}), 200
            auth_svc = CustomerAuthService()
            customer = auth_svc.get_by_email(customer_email)
            if not customer:
                return jsonify({"received": True}), 200
            credits = int(customer.get("referral_discount_credits") or 0)
            if credits <= 0:
                return jsonify({"received": True}), 200
            reward_svc = ReferralRewardService()
            if reward_svc.has_redeemed_for_invoice(invoice_id):
                return jsonify({"received": True}), 200
            coupon_id = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
            if not coupon_id:
                return jsonify({"received": True}), 200
            try:
                import stripe
                stripe.api_key = Config.STRIPE_SECRET_KEY
                stripe.Invoice.modify(
                    invoice_id,
                    discounts=[{"coupon": coupon_id}],
                )
            except Exception as e:
                print(f"[Stripe webhook] invoice.created: failed to apply referrer discount to {invoice_id[:20]}...: {e}")
                return jsonify({"received": True}), 200
            auth_svc.decrement_referral_discount_credits(str(customer["id"]))
            reward_svc.record_redemption(str(customer["id"]), invoice_id)
            print(f"[Stripe webhook] invoice.created: applied referrer 10% to invoice {invoice_id[:20]}... for {customer_email}")
            return jsonify({"received": True}), 200

        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not session or not isinstance(session, dict):
                print("[Stripe webhook] checkout.session.completed: missing or invalid session object; skipping.")
                return jsonify({"received": True}), 200
            amount = session.get("amount_total")
            meta = (session.get("metadata") or {}) if isinstance(session.get("metadata"), dict) else {}
            is_captions = _is_captions_payment(session)
            is_captions_sub = _is_captions_subscription_payment(session)
            print(f"[Stripe webhook] checkout.session.completed amount_total={amount} metadata={meta} is_captions={is_captions} is_captions_sub={is_captions_sub}")
            if is_captions or is_captions_sub:
                try:
                    _handle_captions_payment(session)
                except Exception as e:
                    import traceback
                    print(f"[Stripe webhook] CAPTIONS HANDLER FAILED: {e}")
                    traceback.print_exc()
                    detail = (str(e) or repr(e))[:400]
                    detail = "".join(c for c in detail if ord(c) < 128)
                    return jsonify({"error": "Handler failed", "detail": detail or "Unknown error"}), 500
            else:
                print("[Stripe webhook] Not a captions payment; no action.")

        return jsonify({"received": True}), 200
    except Exception as e:
        import traceback
        print(f"[Stripe webhook] UNEXPECTED ERROR: {e}")
        traceback.print_exc()
        detail = (str(e) or repr(e))[:400]
        detail = "".join(c for c in detail if ord(c) < 128)
        return jsonify({"error": "Internal server error", "detail": detail or "Unknown"}), 500

@webhook_bp.route('/typeform', methods=['POST'])
def typeform_webhook():
    """
    Handle Typeform webhook submissions.
    Maps Typeform response format to our lead format.
    """
    try:
        data = request.get_json()
        
        # Typeform webhook format
        # Extract answers from form_response
        if 'form_response' not in data:
            return jsonify({'error': 'Invalid Typeform webhook format'}), 400
        
        form_response = data['form_response']
        answers = form_response.get('answers', [])
        
        # Map Typeform answers to lead fields
        # This assumes specific field IDs - adjust based on your Typeform
        lead_data = {
            'name': '',
            'email': '',
            'phone': '',
            'service_type': '',
            'message': '',
            'source': 'typeform'
        }
        
        # Typeform answers are in a specific format
        # You'll need to map based on your form structure
        for answer in answers:
            field_type = answer.get('type')
            field_ref = answer.get('field', {}).get('ref', '')
            
            if field_type == 'text' or field_type == 'short_text':
                value = answer.get('text', '')
                # Map based on your form field IDs
                if 'name' in field_ref.lower() or not lead_data['name']:
                    lead_data['name'] = value
                elif 'email' in field_ref.lower() or '@' in value:
                    lead_data['email'] = value
                elif 'phone' in field_ref.lower() or any(c.isdigit() for c in value):
                    lead_data['phone'] = value
                elif 'message' in field_ref.lower() or 'description' in field_ref.lower():
                    lead_data['message'] = value
            
            elif field_type == 'choice':
                value = answer.get('choice', {}).get('label', '')
                if 'service' in field_ref.lower():
                    lead_data['service_type'] = value
        
        # Use the capture_lead function
        from flask import current_app
        with current_app.test_request_context(
            '/api/capture',
            method='POST',
            json=lead_data
        ):
            return capture_lead()
        
    except Exception as e:
        print(f"Error processing Typeform webhook: {e}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/zapier', methods=['POST'])
def zapier_webhook():
    """
    Handle Zapier webhook submissions.
    Generic webhook that accepts standard lead format.
    """
    try:
        data = request.get_json()
        
        # Zapier typically sends data in a clean format
        lead_data = {
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'service_type': data.get('service_type', ''),
            'message': data.get('message', ''),
            'source': data.get('source', 'zapier')
        }
        
        # Use the capture_lead function
        from flask import current_app
        with current_app.test_request_context(
            '/api/capture',
            method='POST',
            json=lead_data
        ):
            return capture_lead()
        
    except Exception as e:
        print(f"Error processing Zapier webhook: {e}")
        return jsonify({'error': str(e)}), 500

@webhook_bp.route('/sendgrid-inbound', methods=['POST'])
def sendgrid_inbound():
    """
    SendGrid Inbound Parse endpoint. DFD/Chat removed — return 200 so SendGrid doesn't retry.
    """
    return "", 200


@webhook_bp.route('/generic', methods=['POST'])
def generic_webhook():
    """
    Generic webhook endpoint that accepts any JSON format.
    Attempts to intelligently map fields.
    """
    try:
        data = request.get_json()
        
        # Intelligent field mapping
        lead_data = {
            'name': data.get('name') or data.get('full_name') or data.get('contact_name', ''),
            'email': data.get('email') or data.get('email_address', ''),
            'phone': data.get('phone') or data.get('phone_number') or data.get('mobile', ''),
            'service_type': data.get('service_type') or data.get('service') or data.get('product', ''),
            'message': data.get('message') or data.get('description') or data.get('notes', ''),
            'source': data.get('source', 'webhook')
        }
        
        # Use the capture_lead function
        from flask import current_app
        with current_app.test_request_context(
            '/api/capture',
            method='POST',
            json=lead_data
        ):
            return capture_lead()
        
    except Exception as e:
        print(f"Error processing generic webhook: {e}")
        return jsonify({'error': str(e)}), 500
