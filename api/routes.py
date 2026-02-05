"""
API routes for lead capture and management.
"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from models.lead import Lead
from services.ai_qualifier import AIQualifier
from services.booking import BookingService
from services.notifications import NotificationService
from services.crm import CRMService
from config import Config
from api.business_routes import get_current_business, businesses_store

api_bp = Blueprint('api', __name__, url_prefix='/api')

def get_business_from_request():
    """Get business from API key or session"""
    # Try API key first
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if api_key:
        for business in businesses_store.values():
            if business.api_key == api_key:
                return business
    
    # Try session
    return get_current_business()

# Initialize services
ai_qualifier = None
booking_service = None
notification_service = None
crm_service = None

def init_services():
    """Initialize services (called after app startup)"""
    global ai_qualifier, booking_service, notification_service, crm_service
    
    try:
        ai_qualifier = AIQualifier()
    except Exception as e:
        print(f"Warning: AI qualifier not available: {e}")
    
    booking_service = BookingService()
    notification_service = NotificationService()
    
    try:
        crm_service = CRMService()
    except Exception as e:
        print(f"Warning: CRM service not available: {e}")

def _front_desk_base_url():
    """Base URL for links in emails (sanitized)."""
    import re
    base = (Config.BASE_URL or "").strip().rstrip("/")
    base = re.sub(r"[\x00-\x1f\x7f]", "", base) if base else "https://lumo-22-production.up.railway.app"
    if base and not base.startswith("http"):
        base = "https://" + base
    return base


@api_bp.route('/front-desk-setup', methods=['POST'])
def front_desk_setup():
    """
    Receive Digital Front Desk setup form, or chat-only setup completion.
    - Full Front Desk: creates new setup, emails you + customer.
    - Chat-only (product=chat, setup_token=t): updates pending row, returns embed code.
    """
    try:
        data = request.get_json() or {}
        product = (data.get('product') or '').strip().lower()
        setup_token = (data.get('setup_token') or '').strip()

        # Chat-only: complete pending setup and return embed code
        if product == 'chat' and setup_token:
            business_name = (data.get('business_name') or '').strip()
            enquiry_email = (data.get('enquiry_email') or '').strip()
            booking_link = (data.get('booking_link') or '').strip() or None
            business_description = (data.get('business_description') or '').strip() or None
            if not business_name or not enquiry_email:
                return jsonify({'ok': False, 'error': 'Please fill in business name and enquiry email.'}), 400
            if '@' not in enquiry_email:
                return jsonify({'ok': False, 'error': 'Please enter a valid enquiry email.'}), 400
            try:
                from services.front_desk_setup_service import FrontDeskSetupService
                svc = FrontDeskSetupService()
                setup = svc.complete_chat_only_setup(
                    done_token=setup_token,
                    business_name=business_name,
                    enquiry_email=enquiry_email,
                    booking_link=booking_link,
                    business_description=business_description,
                )
            except Exception as db_err:
                print(f"[front-desk-setup] Chat complete failed: {db_err}")
                return jsonify({'ok': False, 'error': 'Invalid or expired setup link. Please use the link from your email.'}), 400
            if not setup:
                return jsonify({'ok': False, 'error': 'Invalid or expired setup link. Please use the link from your email.'}), 400
            base = _front_desk_base_url()
            widget_key = setup.get('chat_widget_key') or ''
            # Embed snippet: script loads widget; key identifies the setup. TODO: actual embed.js URL when widget exists.
            embed_snippet = f'<script src="{base}/static/js/chat-widget.js" data-key="{widget_key}" async></script>'
            return jsonify({
                'ok': True,
                'product': 'chat',
                'chat_widget_key': widget_key,
                'embed_snippet': embed_snippet,
            }), 200

        # Full Front Desk: create new setup
        customer_email = (data.get('customer_email') or '').strip()
        business_name = (data.get('business_name') or '').strip()
        enquiry_email = (data.get('enquiry_email') or '').strip()
        booking_link = (data.get('booking_link') or '').strip() or None
        if not customer_email or not business_name or not enquiry_email:
            return jsonify({'ok': False, 'error': 'Please fill in your email, business name, and enquiry email.'}), 400
        if '@' not in customer_email or '@' not in enquiry_email:
            return jsonify({'ok': False, 'error': 'Please enter valid email addresses.'}), 400

        try:
            from services.front_desk_setup_service import FrontDeskSetupService
            svc = FrontDeskSetupService()
            setup = svc.create(
                customer_email=customer_email,
                business_name=business_name,
                enquiry_email=enquiry_email,
                booking_link=booking_link,
            )
            done_token = setup.get("done_token")
            forwarding_email = setup.get("forwarding_email") or ""
            base = _front_desk_base_url()
            mark_connected_url = f"{base}/front-desk-setup-done?t={done_token}" if done_token else None
        except Exception as db_err:
            print(f"[front-desk-setup] DB save failed: {db_err}")
            mark_connected_url = None
            forwarding_email = ""

        to_business = Config.FROM_EMAIL or 'hello@lumo22.com'
        subject_business = f"Digital Front Desk setup: {business_name}"
        body_business = f"""New Digital Front Desk setup submitted:

Customer email: {customer_email}
Business name: {business_name}
Enquiry email to monitor: {enquiry_email}
Booking link: {booking_link or '(none)'}
Forwarding address (for auto-reply): {forwarding_email or '(not set)'}

Forward enquiries to the forwarding address above and we'll auto-reply. When done, click below to mark as connected.
"""
        if mark_connected_url:
            body_business += f"""

Mark as connected (one click):
{mark_connected_url}
"""

        notif = NotificationService()
        ok1 = notif.send_email(to_business, subject_business, body_business)
        if not ok1:
            return jsonify({'ok': False, 'error': 'Could not send setup. Please try again or email hello@lumo22.com.'}), 500

        # Confirmation to customer: include their unique forwarding address so they can forward enquiries for auto-reply
        subject_customer = "Your Digital Front Desk setup — next step"
        body_customer = f"""Hi,

Thanks for submitting your setup for {business_name}.

Your unique forwarding address for auto-replies is:

  {forwarding_email or "(we'll email it to you separately)"}

Forward any enquiry emails to this address and we'll send a professional reply on your behalf (you can set up a rule in your email client to forward from {enquiry_email} to the address above). We'll be in touch if we need anything else.

Lumo 22
"""
        notif.send_email(customer_email, subject_customer, body_customer)

        return jsonify({'ok': True}), 200
    except Exception as e:
        print(f"[front-desk-setup] Error: {e}")
        return jsonify({'ok': False, 'error': 'Something went wrong. Please try again.'}), 500




@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'services': {
            'ai_qualifier': ai_qualifier is not None,
            'booking': booking_service is not None,
            'notifications': notification_service is not None,
            'crm': crm_service is not None
        }
    })

@api_bp.route('/capture', methods=['POST'])
def capture_lead():
    """
    Capture a new lead.
    
    Expected JSON:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "service_type": "Consultation",
        "message": "I need help with...",
        "source": "web_form" (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get business (from API key or session)
        business = get_business_from_request()
        
        if not business:
            return jsonify({'error': 'Authentication required. Provide X-API-Key header or login first.'}), 401
        
        # Create lead object (tied to business)
        lead = Lead(
            name=data.get('name', '').strip(),
            email=data.get('email', '').strip(),
            phone=data.get('phone', '').strip(),
            service_type=data.get('service_type', '').strip(),
            message=data.get('message', '').strip(),
            business_id=business.business_id,  # Link to business
            source=data.get('source', 'web_form')
        )
        
        # Validate
        is_valid, error = lead.validate()
        if not is_valid:
            return jsonify({'error': error}), 400
        
        # Qualify with AI
        if ai_qualifier:
            qualification = ai_qualifier.qualify_lead(
                lead.name,
                lead.email,
                lead.phone,
                lead.service_type,
                lead.message
            )
            lead.qualification_score = qualification['qualification_score']
            lead.qualification_details = qualification
        
        # Determine status
        if lead.is_qualified(Config.MIN_QUALIFICATION_SCORE):
            lead.status = 'qualified'
        else:
            lead.status = 'new'
        
        # Create booking link if qualified and auto-booking enabled
        booking_link = None
        if lead.is_qualified(Config.MIN_QUALIFICATION_SCORE) and Config.AUTO_BOOK_ENABLED:
            booking_result = booking_service.create_booking_link(
                lead.email,
                lead.name,
                lead.service_type,
                lead.message
            )
            booking_link = booking_result.get('booking_link')
            lead.booking_link = booking_link
        
        # Save to CRM
        if crm_service:
            lead_id = crm_service.create_lead(lead)
            lead.lead_id = lead_id
        else:
            # Fallback: generate ID even without CRM
            import uuid
            lead.lead_id = str(uuid.uuid4())
        
        # Send notifications
        if notification_service:
            # Notify lead
            notification_service.send_lead_notification(
                lead.email,
                lead.name,
                lead.service_type,
                booking_link
            )
            
            # Notify business owner (if admin email configured)
            admin_email = request.headers.get('X-Admin-Email') or Config.FROM_EMAIL
            notification_service.send_internal_notification(
                admin_email,
                lead.name,
                lead.email,
                lead.service_type,
                lead.qualification_score or 0,
                booking_link
            )
        
        return jsonify({
            'success': True,
            'lead_id': lead.lead_id,
            'qualification_score': lead.qualification_score,
            'status': lead.status,
            'booking_link': booking_link,
            'message': 'Lead captured and qualified successfully'
        }), 201
        
    except Exception as e:
        print(f"Error capturing lead: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/leads', methods=['GET'])
def get_leads():
    """Get leads for current business (with optional filtering)"""
    try:
        # Get current business
        business = get_business_from_request()
        if not business:
            return jsonify({'error': 'Authentication required'}), 401
        
        if not crm_service:
            return jsonify({'error': 'CRM service not available'}), 503
        
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        
        # Get leads filtered by business_id
        if status:
            leads = crm_service.get_leads_by_status(status, business.business_id, limit)
        else:
            leads = crm_service.get_all_leads(business.business_id, limit)
        
        return jsonify({
            'success': True,
            'count': len(leads),
            'leads': [lead.to_dict() for lead in leads]
        }), 200
        
    except Exception as e:
        print(f"Error retrieving leads: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/leads/<lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Get a specific lead by ID"""
    try:
        if not crm_service:
            return jsonify({'error': 'CRM service not available'}), 503
        
        lead = crm_service.get_lead(lead_id)
        
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404
        
        return jsonify({
            'success': True,
            'lead': lead.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Error retrieving lead: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/leads/<lead_id>/status', methods=['PATCH'])
def update_lead_status(lead_id):
    """Update lead status"""
    try:
        if not crm_service:
            return jsonify({'error': 'CRM service not available'}), 503
        
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        success = crm_service.update_lead_status(lead_id, new_status)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Status updated successfully'
            }), 200
        else:
            return jsonify({'error': 'Failed to update status'}), 500
        
    except Exception as e:
        print(f"Error updating lead status: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/qualify', methods=['POST'])
def qualify_existing_lead():
    """
    Re-qualify an existing lead (useful for testing or updates).
    
    Expected JSON:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "service_type": "Consultation",
        "message": "I need help with..."
    }
    """
    try:
        if not ai_qualifier:
            return jsonify({'error': 'AI qualifier not available'}), 503
        
        data = request.get_json()
        
        qualification = ai_qualifier.qualify_lead(
            data.get('name', ''),
            data.get('email', ''),
            data.get('phone', ''),
            data.get('service_type', ''),
            data.get('message', '')
        )
        
        return jsonify({
            'success': True,
            'qualification': qualification
        }), 200
        
    except Exception as e:
        print(f"Error qualifying lead: {e}")
        return jsonify({'error': str(e)}), 500
