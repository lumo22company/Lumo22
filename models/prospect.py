"""
Prospect model for tracking service businesses to sell to.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json

class Prospect:
    """Prospect business model"""
    
    def __init__(
        self,
        name: str,
        service_type: str,
        location: str,
        contact_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        source: str = 'manual',
        status: str = 'new',
        prospect_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        self.prospect_id = prospect_id
        self.name = name
        self.service_type = service_type
        self.location = location
        self.contact_name = contact_name
        self.email = email
        self.phone = phone
        self.website = website
        self.source = source
        self.status = status  # new, contacted, interested, demo_scheduled, converted, lost
        self.created_at = created_at or datetime.utcnow()
        self.last_contacted = None
        self.outreach_sequence = {}
        self.notes = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert prospect to dictionary"""
        return {
            'prospect_id': self.prospect_id,
            'name': self.name,
            'service_type': self.service_type,
            'location': self.location,
            'contact_name': self.contact_name,
            'email': self.email,
            'phone': self.phone,
            'website': self.website,
            'source': self.source,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_contacted': self.last_contacted.isoformat() if self.last_contacted else None,
            'outreach_sequence': json.dumps(self.outreach_sequence) if isinstance(self.outreach_sequence, dict) else self.outreach_sequence,
            'notes': json.dumps(self.notes) if isinstance(self.notes, list) else self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Prospect':
        """Create prospect from dictionary"""
        prospect = cls(
            name=data.get('name', ''),
            service_type=data.get('service_type', ''),
            location=data.get('location', ''),
            contact_name=data.get('contact_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            website=data.get('website'),
            source=data.get('source', 'manual'),
            status=data.get('status', 'new'),
            prospect_id=data.get('prospect_id'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )
        
        if data.get('last_contacted'):
            prospect.last_contacted = datetime.fromisoformat(data['last_contacted'])
        
        # Parse JSON fields
        outreach = data.get('outreach_sequence')
        if isinstance(outreach, str):
            try:
                prospect.outreach_sequence = json.loads(outreach)
            except:
                prospect.outreach_sequence = {}
        elif isinstance(outreach, dict):
            prospect.outreach_sequence = outreach
        
        notes = data.get('notes')
        if isinstance(notes, str):
            try:
                prospect.notes = json.loads(notes)
            except:
                prospect.notes = []
        elif isinstance(notes, list):
            prospect.notes = notes
        
        return prospect
