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
            enquiry_types = data.get('enquiry_types')
            if isinstance(enquiry_types, list):
                enquiry_types = [str(x).strip() for x in enquiry_types if x]
            else:
                enquiry_types = None
            opening_hours = (data.get('opening_hours') or '').strip() or None
            reply_same_day = bool(data.get('reply_same_day'))
            reply_24h = bool(data.get('reply_24h'))
            tone = (data.get('tone') or '').strip() or None
            good_lead_rules = (data.get('good_lead_rules') or '').strip() or None
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
                    enquiry_types=enquiry_types,
                    opening_hours=opening_hours,
                    reply_same_day=reply_same_day,
                    reply_24h=reply_24h,
                    tone=tone,
                    good_lead_rules=good_lead_rules,
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
                'customer_email': (setup.get('customer_email') or enquiry_email or '').strip(),
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

        tone = (data.get('tone') or '').strip() or None
        reply_style_examples = (data.get('reply_style_examples') or '').strip() or None
        tight_scheduling_enabled = bool(data.get('tight_scheduling_enabled'))
        raw_gap = data.get('minimum_gap_between_appointments')
        minimum_gap_between_appointments = 60
        if raw_gap is not None:
            try:
                minimum_gap_between_appointments = max(15, min(480, int(raw_gap)))
            except (TypeError, ValueError):
                pass
        raw_duration = data.get('appointment_duration_minutes')
        appointment_duration_minutes = 60
        if raw_duration is not None:
            try:
                appointment_duration_minutes = max(15, min(120, int(raw_duration)))
            except (TypeError, ValueError):
                pass
        auto_reply_enabled = data.get('auto_reply_enabled', True)
        if isinstance(auto_reply_enabled, str):
            auto_reply_enabled = auto_reply_enabled.strip().lower() in ('1', 'true', 'yes', 'on')
        else:
            auto_reply_enabled = bool(auto_reply_enabled)
        skip_reply_domains = (data.get('skip_reply_domains') or '').strip() or None
        try:
            from services.front_desk_setup_service import FrontDeskSetupService
            svc = FrontDeskSetupService()
            setup = svc.create(
                customer_email=customer_email,
                business_name=business_name,
                enquiry_email=enquiry_email,
                booking_link=booking_link,
                tone=tone,
                reply_style_examples=reply_style_examples,
                tight_scheduling_enabled=tight_scheduling_enabled,
                minimum_gap_between_appointments=minimum_gap_between_appointments,
                appointment_duration_minutes=appointment_duration_minutes,
                auto_reply_enabled=auto_reply_enabled,
                skip_reply_domains=skip_reply_domains,
            )
            forwarding_email = setup.get("forwarding_email") or ""
        except Exception as db_err:
            print(f"[front-desk-setup] DB save failed: {db_err}")
            forwarding_email = ""

        to_business = Config.FROM_EMAIL or 'hello@lumo22.com'
        subject_business = f"Digital Front Desk setup: {business_name}"
        body_business = f"""New Digital Front Desk setup submitted:

Customer email: {customer_email}
Business name: {business_name}
Enquiry email to monitor: {enquiry_email}
Booking link: {booking_link or '(none)'}
Appointment duration (from their booking system): {appointment_duration_minutes} min
Reply tone: {tone or '(default)'}
Forwarding address (for auto-reply): {forwarding_email or '(not set)'}
Auto-reply: {'on' if auto_reply_enabled else 'off (customer will use pause link to turn on)'}
Skip reply domains (only reply to external): {skip_reply_domains or '(none)'}

Forward enquiries to the forwarding address above and we'll auto-reply. No action needed from you — the setup is already active.
"""

        notif = NotificationService()
        ok1 = notif.send_email(to_business, subject_business, body_business)
        if not ok1:
            return jsonify({'ok': False, 'error': 'Could not send setup. Please try again or email hello@lumo22.com.'}), 500

        # Confirmation to customer: forwarding address + pause/resume links so they can handle emails manually when they want
        subject_customer = "Your Digital Front Desk setup — next step"
        base = _front_desk_base_url()
        pause_url = f"{base}/api/front-desk-setup/pause-auto-reply?token={setup.get('done_token', '')}"
        resume_url = f"{base}/api/front-desk-setup/resume-auto-reply?token={setup.get('done_token', '')}"
        body_customer = f"""Hi,

Thanks for submitting your setup for {business_name}.

Your unique forwarding address for auto-replies is:

  {forwarding_email or "(we'll email it to you separately)"}

Forward any enquiry emails to this address and we'll send a professional reply on your behalf (you can set up a rule in your email client to forward from {enquiry_email} to the address above).

When you want to handle emails yourself, turn auto-reply off (no new auto-replies will be sent until you turn it back on):
  {pause_url}

To turn auto-reply back on:
  {resume_url}

We'll be in touch if we need anything else.

Lumo 22
"""
        notif.send_email(customer_email, subject_customer, body_customer)

        return jsonify({'ok': True, 'customer_email': customer_email}), 200
    except Exception as e:
        print(f"[front-desk-setup] Error: {e}")
        return jsonify({'ok': False, 'error': 'Something went wrong. Please try again.'}), 500


@api_bp.route('/front-desk-setup/pause-auto-reply', methods=['GET'])
def front_desk_pause_auto_reply():
    """Turn off auto-reply for this setup (customer handles emails manually). Token in query: token=."""
    token = (request.args.get('token') or '').strip()
    if not token:
        return _auto_reply_toggle_response(False, "Missing token.")
    try:
        from services.front_desk_setup_service import FrontDeskSetupService
        svc = FrontDeskSetupService()
        ok = svc.set_auto_reply_by_done_token(token, False)
        return _auto_reply_toggle_response(ok, "Auto-reply is now paused." if ok else "Invalid or expired link.")
    except Exception as e:
        print(f"[pause-auto-reply] Error: {e}")
        return _auto_reply_toggle_response(False, "Something went wrong.")


@api_bp.route('/front-desk-setup/resume-auto-reply', methods=['GET'])
def front_desk_resume_auto_reply():
    """Turn auto-reply back on for this setup. Token in query: token=."""
    token = (request.args.get('token') or '').strip()
    if not token:
        return _auto_reply_toggle_response(False, "Missing token.")
    try:
        from services.front_desk_setup_service import FrontDeskSetupService
        svc = FrontDeskSetupService()
        ok = svc.set_auto_reply_by_done_token(token, True)
        return _auto_reply_toggle_response(ok, "Auto-reply is back on." if ok else "Invalid or expired link.")
    except Exception as e:
        print(f"[resume-auto-reply] Error: {e}")
        return _auto_reply_toggle_response(False, "Something went wrong.")


def _auto_reply_toggle_response(success: bool, message: str):
    """Return a simple HTML page for click-from-email links."""
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Digital Front Desk</title></head><body style="font-family: system-ui, sans-serif; max-width: 480px; margin: 3rem auto; padding: 1rem; color: #333;"><p>{message}</p><p><a href="/digital-front-desk">Back to Digital Front Desk</a></p></body></html>"""
    from flask import make_response
    r = make_response(html)
    r.headers["Content-Type"] = "text/html; charset=utf-8"
    return r


@api_bp.route('/chat-widget/status', methods=['GET'])
def chat_widget_status():
    """
    Validate chat widget key. Returns {valid: true/false}.
    Used by embed script so disabled/cancelled subscriptions do not show the bubble.
    Site key (SITE_CHAT_WIDGET_KEY) always returns valid for the Lumo 22 marketing site's demo/help widget.
    """
    from config import Config
    key = (request.args.get("key") or "").strip()
    if not key:
        return jsonify({"valid": False}), 200
    site_key = getattr(Config, "SITE_CHAT_WIDGET_KEY", None)
    if site_key and key == site_key:
        return jsonify({"valid": True}), 200
    try:
        from services.front_desk_setup_service import FrontDeskSetupService
        svc = FrontDeskSetupService()
        setup = svc.get_by_chat_widget_key(key)
        return jsonify({"valid": bool(setup)}), 200
    except Exception:
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

        setup_token = (request.args.get("setup") or "").strip()
        use_setup_config = False
        if setup_token:
            from services.front_desk_setup_service import FrontDeskSetupService
            try:
                svc = FrontDeskSetupService()
                setup = svc.get_by_done_token(setup_token)
                if setup and (setup.get("product_type") or "front_desk") == "front_desk":
                    slot_minutes = max(15, min(120, setup.get("appointment_duration_minutes") or 60))
                    tight_schedule = bool(setup.get("tight_scheduling_enabled"))
                    gap_minutes = max(5, min(480, setup.get("minimum_gap_between_appointments") or 60))
                    use_setup_config = True  # customer cannot override duration/gap from their booking system
            except Exception:
                pass

        if not use_setup_config:
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

        from services.availability import get_available_slots
        from services.appointments_service import get_appointments_for_date

        day = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        existing = get_appointments_for_date(day, default_duration_minutes=slot_minutes)
        slots = get_available_slots(
            date_str,
            existing,
            slot_minutes=slot_minutes,
            work_start=work_start,
            work_end=work_end,
            tight_schedule=tight_schedule,
            gap_minutes=gap_minutes,
        )
        return jsonify({
            "date": date_str[:10],
            "slots": [s.strftime("%H:%M") for s in slots],
            "count": len(slots),
        }), 200
    except Exception as e:
        print(f"[available-slots] Error: {e}")
        return jsonify({"error": "Could not compute slots"}), 500


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
