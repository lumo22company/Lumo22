"""
API routes for managing clients (service businesses using the system).
"""
from flask import Blueprint, request, jsonify, render_template
from models.client import Client
from services.crm import CRMService
import uuid

client_bp = Blueprint('client', __name__, url_prefix='/api/clients')

# In-memory storage for demo (in production, use database)
clients_store = {}

@client_bp.route('', methods=['POST'])
def create_client():
    """
    Create a new client (service business using your system).
    
    Expected JSON:
    {
        "business_name": "ABC Event Planning",
        "contact_email": "owner@abcevents.com",
        "contact_name": "John Doe",
        "service_types": ["Event Planning", "Wedding Planning", "Corporate Events"],
        "tagline": "Making your events unforgettable",
        "logo_url": "https://example.com/logo.png"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create client
        client = Client(
            business_name=data.get('business_name', '').strip(),
            contact_email=data.get('contact_email', '').strip(),
            contact_name=data.get('contact_name', '').strip(),
            service_types=data.get('service_types', []),
            tagline=data.get('tagline', '').strip() or None,
            logo_url=data.get('logo_url', '').strip() or None,
            success_message=data.get('success_message', '').strip() or None
        )
        
        # Validate
        if not client.business_name or not client.contact_email:
            return jsonify({'error': 'business_name and contact_email are required'}), 400
        
        # Store (in production, save to database)
        clients_store[client.client_id] = client
        
        return jsonify({
            'success': True,
            'client': client.to_dict(),
            'message': 'Client created successfully',
            'form_url': f'/client/{client.client_id}/form'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@client_bp.route('', methods=['GET'])
def get_clients():
    """Get all clients"""
    clients = [client.to_dict() for client in clients_store.values()]
    
    return jsonify({
        'success': True,
        'clients': clients,
        'count': len(clients)
    }), 200

@client_bp.route('/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get a specific client"""
    client = clients_store.get(client_id)
    
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    return jsonify({
        'success': True,
        'client': client.to_dict()
    }), 200

@client_bp.route('/<client_id>', methods=['PUT'])
def update_client(client_id):
    """Update a client"""
    client = clients_store.get(client_id)
    
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    data = request.get_json()
    
    # Update fields
    if 'business_name' in data:
        client.business_name = data['business_name']
    if 'contact_email' in data:
        client.contact_email = data['contact_email']
    if 'contact_name' in data:
        client.contact_name = data['contact_name']
    if 'service_types' in data:
        client.service_types = data['service_types']
    if 'tagline' in data:
        client.tagline = data.get('tagline') or None
    if 'logo_url' in data:
        client.logo_url = data.get('logo_url') or None
    if 'success_message' in data:
        client.success_message = data.get('success_message') or None
    
    return jsonify({
        'success': True,
        'client': client.to_dict(),
        'message': 'Client updated successfully'
    }), 200
