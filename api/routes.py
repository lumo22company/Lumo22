"""
API routes (minimal). DFD and chat removed; stubs return 410 for old endpoints.
"""
from flask import Blueprint, request, jsonify, redirect

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/front-desk-setup', methods=['POST'])
def front_desk_setup():
    """DFD discontinued — return 410 Gone."""
    return jsonify({'ok': False, 'error': 'This product is no longer available.'}), 410


@api_bp.route('/front-desk-setup/pause-auto-reply', methods=['GET'])
def front_desk_pause_auto_reply():
    """DFD discontinued — redirect to home."""
    return redirect('/')


@api_bp.route('/front-desk-setup/resume-auto-reply', methods=['GET'])
def front_desk_resume_auto_reply():
    """DFD discontinued — redirect to home."""
    return redirect('/')


@api_bp.route('/chat-widget/status', methods=['GET'])
def chat_widget_status():
    """Chat widget discontinued — always returns valid: false."""
    return jsonify({"valid": False}), 200


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
    }), 200


@api_bp.route('/available-slots', methods=['GET'])
def available_slots():
    """DFD discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410


@api_bp.route('/booking-info', methods=['GET'])
def booking_info():
    """DFD discontinued — always returns null."""
    return jsonify({"booking_link": None, "business_name": None}), 200


@api_bp.route('/capture', methods=['POST'])
def capture_lead():
    """Lead capture (DFD/chat) discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410


@api_bp.route('/leads', methods=['GET'])
def get_leads():
    """Leads API discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410


@api_bp.route('/leads/<lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Leads API discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410


@api_bp.route('/leads/<lead_id>/status', methods=['PATCH'])
def update_lead_status(lead_id):
    """Leads API discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410


@api_bp.route('/qualify', methods=['POST'])
def qualify_existing_lead():
    """AI qualify (chat/DFD) discontinued — return 410."""
    return jsonify({'error': 'This product is no longer available.'}), 410
