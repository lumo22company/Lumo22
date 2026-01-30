"""
Business model - represents a small business that signed up for your SaaS system.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import uuid
import hashlib
import secrets

class Business:
    """Business account using the SaaS booking system"""
    
    def __init__(
        self,
        business_name: str,
        email: str,
        password_hash: Optional[str] = None,
        business_id: Optional[str] = None,
        service_types: Optional[List[str]] = None,
        status: str = 'active',
        subscription_tier: str = 'starter',
        created_at: Optional[datetime] = None,
        api_key: Optional[str] = None
    ):
        self.business_id = business_id or str(uuid.uuid4())
        self.business_name = business_name
        self.email = email
        self.password_hash = password_hash
        self.service_types = service_types or []
        self.status = status  # active, paused, cancelled
        self.subscription_tier = subscription_tier  # starter, pro, enterprise
        self.created_at = created_at or datetime.utcnow()
        self.api_key = api_key or self._generate_api_key()
        self.last_login = None
        
    def _generate_api_key(self) -> str:
        """Generate API key for this business"""
        return f"lum_{secrets.token_urlsafe(32)}"
    
    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password: str) -> bool:
        """Check if password matches"""
        if not self.password_hash:
            return False
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert business to dictionary"""
        data = {
            'business_id': self.business_id,
            'business_name': self.business_name,
            'email': self.email,
            'service_types': json.dumps(self.service_types) if isinstance(self.service_types, list) else self.service_types,
            'status': self.status,
            'subscription_tier': self.subscription_tier,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['api_key'] = self.api_key
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Business':
        """Create business from dictionary"""
        service_types = data.get('service_types', [])
        if isinstance(service_types, str):
            try:
                service_types = json.loads(service_types)
            except:
                service_types = [service_types] if service_types else []
        
        business = cls(
            business_name=data.get('business_name', ''),
            email=data.get('email', ''),
            password_hash=data.get('password_hash'),
            business_id=data.get('business_id'),
            service_types=service_types,
            status=data.get('status', 'active'),
            subscription_tier=data.get('subscription_tier', 'starter'),
            api_key=data.get('api_key')
        )
        
        if data.get('created_at'):
            business.created_at = datetime.fromisoformat(data['created_at'])
        if data.get('last_login'):
            business.last_login = datetime.fromisoformat(data['last_login'])
        
        return business
