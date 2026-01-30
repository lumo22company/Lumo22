"""
Client model - represents a service business that uses your lead automation system.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import uuid

class Client:
    """Client (service business) that uses the lead automation system"""
    
    def __init__(
        self,
        business_name: str,
        contact_email: str,
        contact_name: str,
        service_types: List[str],
        client_id: Optional[str] = None,
        status: str = 'active',
        created_at: Optional[datetime] = None,
        tagline: Optional[str] = None,
        logo_url: Optional[str] = None,
        success_message: Optional[str] = None,
        form_url: Optional[str] = None
    ):
        self.client_id = client_id or str(uuid.uuid4())
        self.business_name = business_name
        self.contact_email = contact_email
        self.contact_name = contact_name
        self.service_types = service_types if isinstance(service_types, list) else [service_types]
        self.status = status  # active, paused, cancelled
        self.created_at = created_at or datetime.utcnow()
        self.tagline = tagline
        self.logo_url = logo_url
        self.success_message = success_message
        self.form_url = form_url or f"/client/{self.client_id}/form"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert client to dictionary"""
        return {
            'client_id': self.client_id,
            'business_name': self.business_name,
            'contact_email': self.contact_email,
            'contact_name': self.contact_name,
            'service_types': json.dumps(self.service_types) if isinstance(self.service_types, list) else self.service_types,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tagline': self.tagline,
            'logo_url': self.logo_url,
            'success_message': self.success_message,
            'form_url': self.form_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Client':
        """Create client from dictionary"""
        service_types = data.get('service_types', [])
        if isinstance(service_types, str):
            try:
                service_types = json.loads(service_types)
            except:
                service_types = [service_types] if service_types else []
        
        client = cls(
            business_name=data.get('business_name', ''),
            contact_email=data.get('contact_email', ''),
            contact_name=data.get('contact_name', ''),
            service_types=service_types,
            client_id=data.get('client_id'),
            status=data.get('status', 'active'),
            tagline=data.get('tagline'),
            logo_url=data.get('logo_url'),
            success_message=data.get('success_message'),
            form_url=data.get('form_url')
        )
        
        if data.get('created_at'):
            client.created_at = datetime.fromisoformat(data['created_at'])
        
        return client
