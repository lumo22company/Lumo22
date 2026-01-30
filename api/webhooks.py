"""
Webhook handlers for third-party integrations.
Allows external services to send leads to the system.
"""
from flask import Blueprint, request, jsonify, current_app
from config import Config
from api.routes import capture_lead

webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# --- Stripe (30 Days Captions) ---
CAPTIONS_AMOUNT_PENCE = 9700  # £97


def _is_captions_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions."""
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "captions":
        return True
    amount = session.get("amount_total") or 0
    if amount == CAPTIONS_AMOUNT_PENCE:
        return True
    price_id = Config.STRIPE_CAPTIONS_PRICE_ID if hasattr(Config, "STRIPE_CAPTIONS_PRICE_ID") else None
    if not price_id:
        return False
    for item in (session.get("line_items") or {}).get("data") or []:
        if item.get("price", {}).get("id") == price_id:
            return True
    return False


def _handle_captions_payment(session):
    """Create caption order and send intake-link email."""
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    customer_email = None
    details = session.get("customer_details") or {}
    if isinstance(details, dict):
        customer_email = details.get("email") or details.get("customer_email")
    if not customer_email:
        customer_email = session.get("customer_email")
    if not customer_email:
        print("Stripe captions webhook: no customer email in session")
        return

    order_service = CaptionOrderService()
    order = order_service.create_order(
        customer_email=customer_email,
        stripe_session_id=session.get("id"),
    )
    token = order["token"]
    base_url = getattr(Config, "BASE_URL", "http://localhost:5001").strip().rstrip("/")
    intake_url = f"{base_url}/captions-intake?t={token}"

    subject = "Your 30 Days of Social Media Captions — next step"
    body = f"""Hi,

Thanks for your order. Your 30 Days of Social Media Captions will be tailored to your business and voice.

Please complete this short form so we can create your captions. It takes about 2 minutes:

{intake_url}

Once you submit, we'll generate your 30 captions and send them to you by email within a few minutes.

If you have any questions, just reply to this email.

Lumo 22
"""
    notif = NotificationService()
    notif.send_email(customer_email, subject, body)


@webhook_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Stripe webhook: checkout.session.completed for 30 Days Captions.
    Create order and send intake-link email.
    """
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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        if _is_captions_payment(session):
            try:
                _handle_captions_payment(session)
            except Exception as e:
                print(f"Stripe captions handler error: {e}")
                return jsonify({"error": "Handler failed"}), 500

    return jsonify({"received": True}), 200

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
