"""
Lead data models and validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json

class Lead:
    """Lead model with validation and serialization"""
    
    def __init__(
        self,
        name: str,
        email: str,
        phone: str,
        service_type: str,
        message: str,
        business_id: str,  # Required - which business this lead belongs to
        source: str = 'web_form',
        qualification_score: Optional[int] = None,
        status: str = 'new',
        created_at: Optional[datetime] = None,
        lead_id: Optional[str] = None
    ):
        self.lead_id = lead_id
        self.business_id = business_id  # Which business owns this lead
        self.name = name
        self.email = email
        self.phone = phone
        self.service_type = service_type
        self.message = message
        self.source = source
        self.qualification_score = qualification_score
        self.status = status  # new, qualified, booked, converted, lost
        self.created_at = created_at or datetime.utcnow()
        self.booked_at = None
        self.booking_link = None
        self.qualification_details = {}
        
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate lead data"""
        if not self.name or len(self.name.strip()) < 2:
            return False, "Name must be at least 2 characters"
        
        if not self.email or '@' not in self.email:
            return False, "Valid email is required"
        
        if not self.phone or len(self.phone.replace(' ', '').replace('-', '').replace('+', '')) < 10:
            return False, "Valid phone number is required"
        
        if not self.service_type:
            return False, "Service type is required"
        
        if not self.message or len(self.message.strip()) < 10:
            return False, "Message must be at least 10 characters"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary for storage"""
        return {
            'lead_id': self.lead_id,
            'business_id': self.business_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'service_type': self.service_type,
            'message': self.message,
            'source': self.source,
            'qualification_score': self.qualification_score,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'booked_at': self.booked_at.isoformat() if self.booked_at else None,
            'booking_link': self.booking_link,
            'qualification_details': json.dumps(self.qualification_details) if isinstance(self.qualification_details, dict) else self.qualification_details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lead':
        """Create lead from dictionary"""
        lead = cls(
            name=data.get('name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            service_type=data.get('service_type', ''),
            message=data.get('message', ''),
            business_id=data.get('business_id', ''),  # Required
            source=data.get('source', 'web_form'),
            qualification_score=data.get('qualification_score'),
            status=data.get('status', 'new'),
            lead_id=data.get('lead_id'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )
        
        if data.get('booked_at'):
            lead.booked_at = datetime.fromisoformat(data['booked_at'])
        
        lead.booking_link = data.get('booking_link')
        
        qual_details = data.get('qualification_details')
        if isinstance(qual_details, str):
            try:
                lead.qualification_details = json.loads(qual_details)
            except:
                lead.qualification_details = {}
        elif isinstance(qual_details, dict):
            lead.qualification_details = qual_details
        
        return lead
    
    def is_qualified(self, min_score: int = 60) -> bool:
        """Check if lead meets qualification threshold"""
        return self.qualification_score is not None and self.qualification_score >= min_score
