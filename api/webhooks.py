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

# --- Stripe (Digital Front Desk) — monthly amounts in pence ---
# Email only: £79, £149, £299. Bundle (tier + £59, 5% off): £131, £198, £340.
FRONT_DESK_AMOUNTS_PENCE = (7900, 14900, 29900, 13100, 19800, 34000)
FRONT_DESK_PLAN_NAMES = {
    7900: "Starter", 14900: "Growth", 29900: "Pro",
    13100: "Starter + Chat", 19800: "Growth + Chat", 34000: "Pro + Chat",
}

# --- Stripe (Chat Assistant) — single fixed price £59/month ---
CHAT_AMOUNTS_PENCE = (5900,)


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
    sub_price_id = getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or ""
    if not sub_price_id:
        return False
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = (item.get("price") or {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
        if pid == sub_price_id:
            return True
    return False


def _is_captions_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions (one-off £97)."""
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "captions":
        return True
    amount_raw = session.get("amount_total")
    try:
        amount = int(amount_raw) if amount_raw is not None else 0
    except (TypeError, ValueError):
        amount = 0
    if amount == CAPTIONS_AMOUNT_PENCE:
        return True
    price_id = Config.STRIPE_CAPTIONS_PRICE_ID if hasattr(Config, "STRIPE_CAPTIONS_PRICE_ID") else None
    if price_id:
        for item in (session.get("line_items") or {}).get("data") or []:
            if item.get("price", {}).get("id") == price_id:
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

    order_service = CaptionOrderService()
    # Idempotent: if Stripe retries, we may already have an order for this session
    existing = order_service.get_by_stripe_session_id(session_id) if session_id else None
    if existing:
        print(f"[Stripe webhook] Order already exists for session {session_id[:20]}..., resending intake email")
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
            order = order_service.create_order(
                customer_email=customer_email,
                stripe_session_id=session_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
            )
        except Exception as e:
            print(f"[Stripe webhook] Failed to create order in Supabase: {e}")
            raise
        print(f"[Stripe webhook] Order created id={order.get('id')} token=...{order['token'][-6:]}")
    token = order["token"]
    # Use hardcoded URL only — no BASE_URL so env vars can't cause "Invalid non-printable ASCII"
    INTAKE_BASE = "https://lumo-22-production.up.railway.app"
    safe_token = str(token).strip()
    intake_url = f"{INTAKE_BASE}/captions-intake?t={safe_token}"

    subject = "Your 30 Days of Social Media Captions - next step"
    body = f"""Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

{intake_url}

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""

    print(f"[Stripe webhook] Sending intake email to {customer_email}")
    notif = NotificationService()
    ok = False
    try:
        ok = notif.send_email(customer_email, subject, body)
    except Exception as send_err:
        # Always retry with hardcoded URL so env/hidden chars or SendGrid validation can't cause 500
        print(f"[Stripe webhook] Send failed ({send_err}), retrying with hardcoded URL")
        fallback_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={safe_token}"
        fallback_body = f"""Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

{fallback_url}

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""
        try:
            ok = notif.send_email(customer_email, subject, fallback_body)
        except Exception as fallback_err:
            print(f"[Stripe webhook] Fallback send also failed: {fallback_err}")
            raise
    if not ok:
        print(f"[Stripe webhook] intake-link email FAILED to send to {customer_email}")
    else:
        print(f"[Stripe webhook] intake-link email sent to {customer_email}")


def _get_session_amount_total(session):
    """Get amount_total from session; for subscriptions it may be in line_items or require a fetch."""
    amount_raw = session.get("amount_total")
    if amount_raw is not None:
        try:
            return int(amount_raw)
        except (TypeError, ValueError):
            pass
    # Subscription checkout sometimes has amount in line_items (may not be in default webhook payload)
    items = (session.get("line_items") or {}).get("data") if isinstance(session.get("line_items"), dict) else None
    if items and len(items) > 0:
        first = items[0]
        amt = first.get("amount_total") if isinstance(first, dict) else getattr(first, "amount_total", None)
        if amt is not None:
            try:
                return int(amt)
            except (TypeError, ValueError):
                pass
    # Fetch session with line_items if amount still missing (e.g. subscription, Stripe didn't expand)
    try:
        import stripe
        sid = session.get("id") if hasattr(session, "get") else getattr(session, "id", None)
        if Config.STRIPE_SECRET_KEY and sid:
            stripe.api_key = Config.STRIPE_SECRET_KEY
            full = stripe.checkout.Session.retrieve(sid, expand=["line_items"])
            amount_raw = full.get("amount_total")
            if amount_raw is not None:
                return int(amount_raw)
            items = (full.get("line_items") or {}).get("data") if isinstance(full.get("line_items"), dict) else None
            if items and len(items) > 0:
                amt = items[0].get("amount_total") if isinstance(items[0], dict) else getattr(items[0], "amount_total", None)
                if amt is not None:
                    return int(amt)
    except Exception as e:
        print(f"[Stripe webhook] Could not retrieve session for amount_total: {e}")
    return None


def _is_front_desk_payment(session):
    """True if this checkout is for Digital Front Desk (Starter £79, Growth £149, Pro £299 monthly)."""
    if _is_captions_payment(session):
        return False
    if _is_chat_payment(session):
        return False
    amount = _get_session_amount_total(session)
    if amount is None:
        print("[Stripe webhook] Front Desk: amount_total missing in session; not matching.")
        return False
    currency = (session.get("currency") or "gbp").lower()
    if currency != "gbp":
        print(f"[Stripe webhook] Front Desk: currency={currency} not GBP; not matching.")
        return False
    if amount not in FRONT_DESK_AMOUNTS_PENCE:
        print(f"[Stripe webhook] Front Desk: amount={amount} not in {FRONT_DESK_AMOUNTS_PENCE}; not matching.")
        return False
    return True


def _is_chat_payment(session):
    """True if this checkout is for Chat Assistant (£59/month)."""
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "chat":
        print("[Stripe webhook] Chat: matched by metadata product=chat")
        return True
    amount = _get_session_amount_total(session)
    if amount is None:
        return False
    currency = (session.get("currency") or "gbp").lower()
    if currency != "gbp":
        return False
    if amount in CHAT_AMOUNTS_PENCE:
        print(f"[Stripe webhook] Chat: matched by amount={amount} GBP")
        return True
    return False


def _handle_front_desk_payment(session):
    """Send setup email for Digital Front Desk — takes customer through setup straight away."""
    from services.notifications import NotificationService

    customer_email = _get_customer_email_from_session(session)
    if not customer_email:
        print("[Stripe webhook] Front Desk: no customer email in session; setup email not sent. Check Stripe webhook payload or expand customer_details.")
        return
    amount = _get_session_amount_total(session) or 0
    plan_name = FRONT_DESK_PLAN_NAMES.get(amount, "Digital Front Desk")

    base = (Config.BASE_URL or "").strip().rstrip("/")
    base = re.sub(r"[\x00-\x1f\x7f]", "", base) if base else "https://lumo-22-production.up.railway.app"
    if base and not base.startswith("http"):
        base = "https://" + base
    setup_url = f"{base}/front-desk-setup"

    subject = "Your Digital Front Desk — complete your setup"
    body = f"""Hi,

You're on the {plan_name} plan. Complete your setup in 3 steps so we can get you live:

Step 1 — Open your setup form
Click the link below (takes about 2 minutes):

{setup_url}

Step 2 — Enter your details
• Your email (so we can contact you)
• Business name
• The email address you want us to monitor for enquiries (e.g. hello@ or enquiries@)
• Your booking link (Calendly, Fresha, etc.) — if you're on Growth or Pro, or leave blank for now

Step 3 — Submit
We'll receive your details and connect everything. You'll be live within 24 hours.

If anything's unclear, just reply to this email.

Lumo 22
"""

    print(f"[Stripe webhook] Sending Front Desk setup email to {customer_email}")
    notif = NotificationService()
    ok = notif.send_email(customer_email, subject, body)
    if ok:
        print(f"[Stripe webhook] Front Desk setup email sent to {customer_email}")
    else:
        print(f"[Stripe webhook] Front Desk setup email FAILED to send to {customer_email}")


def _handle_chat_payment(session):
    """Create pending chat-only setup and send email with link to complete setup (get embed code)."""
    from services.notifications import NotificationService
    from services.front_desk_setup_service import FrontDeskSetupService

    customer_email = _get_customer_email_from_session(session)
    if not customer_email:
        print("[Stripe webhook] Chat: no customer email in session; setup email not sent.")
        return
    print(f"[Stripe webhook] Chat: handling payment for {customer_email}")
    svc = FrontDeskSetupService()
    try:
        setup = svc.create_chat_only_pending(customer_email)
    except Exception as e:
        print(f"[Stripe webhook] Chat: create_chat_only_pending failed: {e}")
        raise
    done_token = setup.get("done_token")
    if not done_token:
        print("[Stripe webhook] Chat: no done_token after create.")
        return
    base = (Config.BASE_URL or "").strip().rstrip("/")
    base = re.sub(r"[\x00-\x1f\x7f]", "", base) if base else "https://lumo-22-production.up.railway.app"
    if base and not base.startswith("http"):
        base = "https://" + base
    setup_url = f"{base}/front-desk-setup?product=chat&t={done_token}"

    subject = "Your Website Chat Widget — complete your setup"
    body = f"""Hi,

Thanks for signing up for the Website Chat Widget. Complete your setup in 2 minutes to get your embed code:

{setup_url}

You'll enter:
• Your business name
• Where to send leads (email address)
• Optional: booking link, short description of your business

Once you submit, we'll show your embed code — add it to your website and your chat will go live.

If anything's unclear, just reply to this email.

Lumo 22
"""
    print(f"[Stripe webhook] Sending Chat setup email to {customer_email}")
    notif = NotificationService()
    ok = notif.send_email(customer_email, subject, body)
    if ok:
        print(f"[Stripe webhook] Chat setup email sent to {customer_email}")
    else:
        print(f"[Stripe webhook] Chat setup email FAILED to send to {customer_email}")


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
        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not session or not isinstance(session, dict):
                print("[Stripe webhook] checkout.session.completed: missing or invalid session object; skipping.")
                return jsonify({"received": True}), 200
            amount = session.get("amount_total")
            meta = (session.get("metadata") or {}) if isinstance(session.get("metadata"), dict) else {}
            is_captions = _is_captions_payment(session)
            is_captions_sub = _is_captions_subscription_payment(session)
            is_chat = _is_chat_payment(session)
            is_front_desk = _is_front_desk_payment(session)
            print(f"[Stripe webhook] checkout.session.completed amount_total={amount} metadata={meta} is_captions={is_captions} is_captions_sub={is_captions_sub} is_chat={is_chat} is_front_desk={is_front_desk}")
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
            elif is_chat:
                try:
                    _handle_chat_payment(session)
                except Exception as e:
                    import traceback
                    print(f"[Stripe webhook] CHAT HANDLER FAILED: {e}")
                    traceback.print_exc()
                    detail = (str(e) or repr(e))[:400]
                    detail = "".join(c for c in detail if ord(c) < 128)
                    return jsonify({"error": "Handler failed", "detail": detail or "Unknown error"}), 500
            elif is_front_desk:
                try:
                    _handle_front_desk_payment(session)
                except Exception as e:
                    import traceback
                    print(f"[Stripe webhook] FRONT DESK HANDLER FAILED: {e}")
                    traceback.print_exc()
                    detail = (str(e) or repr(e))[:400]
                    detail = "".join(c for c in detail if ord(c) < 128)
                    return jsonify({"error": "Handler failed", "detail": detail or "Unknown error"}), 500
            else:
                print("[Stripe webhook] Not captions, chat, or Front Desk payment; no action.")

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
    SendGrid Inbound Parse: receives parsed inbound email as multipart/form-data.
    Look up front_desk_setups by recipient (forwarding_email), generate reply with OpenAI, send via SendGrid.
    """
    try:
        # SendGrid sends: to, from, subject, text, html, envelope, etc.
        to_addr = request.form.get("to", "").strip()
        from_addr = request.form.get("from", "").strip()
        subject = request.form.get("subject", "").strip()
        text = request.form.get("text", "").strip()
        html = request.form.get("html", "").strip()
        if not to_addr:
            print("[SendGrid inbound] Missing 'to'")
            return "", 400
        from services.inbound_reply_service import process_inbound
        ok = process_inbound(to_addr=to_addr, from_addr=from_addr, subject=subject, text=text, html=html)
        # Inbound Parse expects 200 to stop retries
        return "", 200
    except Exception as e:
        print(f"[SendGrid inbound] Error: {e}")
        import traceback
        traceback.print_exc()
        return "", 500


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
