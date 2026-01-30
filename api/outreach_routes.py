"""
API routes for outreach and prospecting.
"""
from flask import Blueprint, request, jsonify
from services.prospecting import BusinessProspector
from services.outreach import OutreachService
from models.prospect import Prospect
from services.crm import CRMService
from config import Config
import uuid

outreach_bp = Blueprint('outreach', __name__, url_prefix='/api/outreach')

# Initialize services
prospector = BusinessProspector()
outreach_service = OutreachService()
crm_service = None

def init_outreach_services():
    """Initialize outreach services"""
    global crm_service
    try:
        crm_service = CRMService()
    except:
        pass

@outreach_bp.route('/prospects', methods=['POST'])
def create_prospect():
    """
    Add a new prospect manually.
    
    Expected JSON:
    {
        "name": "Business Name",
        "service_type": "Event Planning",
        "location": "London, UK",
        "contact_name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "website": "https://example.com"
    }
    """
    try:
        data = request.get_json()
        
        prospect = Prospect(
            name=data.get('name', '').strip(),
            service_type=data.get('service_type', '').strip(),
            location=data.get('location', '').strip(),
            contact_name=data.get('contact_name', '').strip() or None,
            email=data.get('email', '').strip() or None,
            phone=data.get('phone', '').strip() or None,
            website=data.get('website', '').strip() or None,
            source=data.get('source', 'manual')
        )
        
        if not prospect.prospect_id:
            prospect.prospect_id = str(uuid.uuid4())
        
        # Save to database (would need prospects table)
        # For now, return the prospect
        
        return jsonify({
            'success': True,
            'prospect': prospect.to_dict(),
            'message': 'Prospect created successfully'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@outreach_bp.route('/prospects', methods=['GET'])
def get_prospects():
    """Get all prospects"""
    # In production, fetch from database
    return jsonify({
        'success': True,
        'prospects': [],
        'count': 0
    }), 200

@outreach_bp.route('/prospects/<prospect_id>/outreach', methods=['POST'])
def schedule_outreach(prospect_id):
    """
    Schedule outreach for a prospect.
    
    Expected JSON:
    {
        "channel": "email" or "linkedin"
    }
    """
    try:
        data = request.get_json() or {}
        channel = data.get('channel', 'email')
        
        # Get prospect (would fetch from database)
        # For now, create example
        prospect_data = {
            'id': prospect_id,
            'name': 'Example Business',
            'service_type': 'Event Planning',
            'location': 'London, UK',
            'contact_name': 'John Doe'
        }
        
        sequence = outreach_service.schedule_outreach(prospect_data, channel)
        
        return jsonify({
            'success': True,
            'outreach_sequence': sequence,
            'message': 'Outreach scheduled successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@outreach_bp.route('/search', methods=['POST'])
def search_businesses():
    """
    Search for service businesses to prospect.
    
    Expected JSON:
    {
        "service_type": "event planner",
        "location": "London, UK",
        "max_results": 50
    }
    """
    try:
        data = request.get_json()
        
        service_type = data.get('service_type', '')
        location = data.get('location', '')
        max_results = int(data.get('max_results', 50))
        
        if not service_type or not location:
            return jsonify({'error': 'service_type and location are required'}), 400
        
        businesses = prospector.find_service_businesses(
            service_type,
            location,
            max_results
        )
        
        return jsonify({
            'success': True,
            'businesses': businesses,
            'count': len(businesses)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
