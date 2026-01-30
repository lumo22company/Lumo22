"""
API routes for business signup, login, and management.
"""
from flask import Blueprint, request, jsonify, session, render_template
from datetime import datetime
from models.business import Business
import uuid

business_bp = Blueprint('business', __name__, url_prefix='/api/business')

# In-memory storage for demo (in production, use database)
businesses_store = {}
sessions_store = {}  # session_id -> business_id

def get_current_business():
    """Get current logged-in business from session"""
    session_id = session.get('session_id')
    if not session_id:
        return None
    
    business_id = sessions_store.get(session_id)
    if not business_id:
        return None
    
    return businesses_store.get(business_id)

@business_bp.route('/signup', methods=['POST'])
def signup():
    """
    Business signup - create new account.
    
    Expected JSON:
    {
        "business_name": "ABC Event Planning",
        "email": "owner@abcevents.com",
        "password": "securepassword123",
        "service_types": ["Event Planning", "Wedding Planning"]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        business_name = data.get('business_name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        service_types = data.get('service_types', [])
        
        # Validate
        if not business_name or not email or not password:
            return jsonify({'error': 'business_name, email, and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Check if email already exists
        for existing in businesses_store.values():
            if existing.email == email:
                return jsonify({'error': 'Email already registered'}), 400
        
        # Create business
        business = Business(
            business_name=business_name,
            email=email,
            service_types=service_types
        )
        business.set_password(password)
        
        # Store
        businesses_store[business.business_id] = business
        
        # Create session
        session_id = str(uuid.uuid4())
        sessions_store[session_id] = business.business_id
        session['session_id'] = session_id
        
        return jsonify({
            'success': True,
            'business': business.to_dict(include_sensitive=True),
            'message': 'Account created successfully',
            'session_id': session_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_bp.route('/login', methods=['POST'])
def login():
    """
    Business login.
    
    Expected JSON:
    {
        "email": "owner@abcevents.com",
        "password": "securepassword123"
    }
    """
    try:
        data = request.get_json()
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find business
        business = None
        for b in businesses_store.values():
            if b.email == email:
                business = b
                break
        
        if not business:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check password
        if not business.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Create session
        session_id = str(uuid.uuid4())
        sessions_store[session_id] = business.business_id
        session['session_id'] = session_id
        
        business.last_login = datetime.utcnow()
        
        return jsonify({
            'success': True,
            'business': business.to_dict(),
            'session_id': session_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_bp.route('/me', methods=['GET'])
def get_current():
    """Get current logged-in business"""
    business = get_current_business()
    
    if not business:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'success': True,
        'business': business.to_dict(include_sensitive=True)
    }), 200

@business_bp.route('/logout', methods=['POST'])
def logout():
    """Logout current business"""
    session_id = session.get('session_id')
    if session_id:
        sessions_store.pop(session_id, None)
        session.pop('session_id', None)
    
    return jsonify({'success': True, 'message': 'Logged out'}), 200
