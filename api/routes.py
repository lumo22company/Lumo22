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

@api_bp.route('/front-desk-setup', methods=['POST'])
def front_desk_setup():
    """DFD discontinued — return 410 Gone."""
    return jsonify({'ok': False, 'error': 'This product is no longer available.'}), 410


@api_bp.route('/front-desk-setup/pause-auto-reply', methods=['GET'])
def front_desk_pause_auto_reply():
    """DFD discontinued — redirect to home."""
    from flask import redirect
    return redirect('/')


@api_bp.route('/front-desk-setup/resume-auto-reply', methods=['GET'])
def front_desk_resume_auto_reply():
    """DFD discontinued — redirect to home."""
    from flask import redirect
    return redirect('/')


@api_bp.route('/chat-widget/status', methods=['GET'])
def chat_widget_status():
    """Chat widget discontinued — always returns valid: false."""
    return jsonify({"valid": False}), 200


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


@api_bp.route('/available-slots', methods=['GET'])
def available_slots():
    """
    Return available appointment slot start times for a given day.
    Query params: date (YYYY-MM-DD), tight_schedule (true|false), gap_minutes (int),
    optional slot_minutes, work_start (HH:MM), work_end (HH:MM).
    Optional setup=TOKEN: use business's appointment_duration_minutes, tight_scheduling, gap from front_desk_setups.
    When tight_schedule is true and there are existing bookings that day, only slots
    within gap_minutes of a booking are returned; if no bookings, all slots are returned.
    """
    try:
        date_str = (request.args.get("date") or "").strip()
        if not date_str:
            return jsonify({"error": "Missing date (use ?date=YYYY-MM-DD)"}), 400
        try:
            datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date; use YYYY-MM-DD"}), 400

        raw_gap = request.args.get("gap_minutes")
        raw_slot = request.args.get("slot_minutes")
        tight_schedule = (request.args.get("tight_schedule") or "").strip().lower() in ("1", "true", "yes")
        gap_minutes = 60
        slot_minutes = 60

        work_start = request.args.get("work_start") or None
        work_end = request.args.get("work_end") or None
        if True:
            if raw_gap is not None:
                try:
                    gap_minutes = max(5, min(480, int(raw_gap)))
                except (TypeError, ValueError):
                    pass
            if raw_slot is not None:
                try:
                    slot_minutes = max(5, min(120, int(raw_slot)))
                except (TypeError, ValueError):
                    pass
            work_start = request.args.get("work_start") or None
            work_end = request.args.get("work_end") or None

        day = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        slots = []

        if not slots:
            from services.availability import get_available_slots
            from services.appointments_service import get_appointments_for_date
            existing = get_appointments_for_date(day, default_duration_minutes=slot_minutes)
            slot_dt_list = get_available_slots(
                date_str,
                existing,
                slot_minutes=slot_minutes,
                work_start=work_start,
                work_end=work_end,
                tight_schedule=tight_schedule,
                gap_minutes=gap_minutes,
            )
            slots = [s.strftime("%H:%M") for s in slot_dt_list]

        slot_strs = slots if slots and isinstance(slots[0], str) else [s.strftime("%H:%M") for s in slots]
        out = {
            "date": date_str[:10],
            "slots": slot_strs,
            "count": len(slot_strs),
        }
        if request.args.get("debug"):
            from services.appointments_service import get_appointments_for_date
            existing = get_appointments_for_date(day, default_duration_minutes=slot_minutes)
            out["existing_bookings"] = len(existing)
        return jsonify(out), 200
    except Exception as e:
        print(f"[available-slots] Error: {e}")
        return jsonify({"error": "Could not compute slots"}), 500


@api_bp.route('/booking-info', methods=['GET'])
def booking_info():
    """DFD discontinued — always returns null."""
    return jsonify({"booking_link": None, "business_name": None}), 200


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
