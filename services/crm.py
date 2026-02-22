"""
CRM service for managing leads in Supabase database.
Handles lead storage, retrieval, and status updates.
"""
from typing import Dict, Any, Optional, List
import re
from supabase import create_client, Client
from datetime import datetime
import uuid
from config import Config
from models.lead import Lead


def _sanitize_supabase_url(u: str) -> str:
    """Remove control chars so httpx doesn't raise InvalidURL."""
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


class CRMService:
    """Service for CRM operations using Supabase"""
    
    def __init__(self):
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_supabase_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        self.client: Client = create_client(url, (Config.SUPABASE_KEY or "").strip())
        self.table_name = 'leads'
    
    def create_lead(self, lead: Lead) -> str:
        """
        Create a new lead in the database.
        
        Returns:
            lead_id (str)
        """
        if not lead.lead_id:
            lead.lead_id = str(uuid.uuid4())
        
        lead_dict = lead.to_dict()
        
        try:
            result = self.client.table(self.table_name).insert(lead_dict).execute()
            
            if result.data:
                return result.data[0].get('lead_id', lead.lead_id)
            return lead.lead_id
            
        except Exception as e:
            print(f"Error creating lead: {e}")
            # If table doesn't exist, we'll handle it in init_db
            raise
    
    def get_lead(self, lead_id: str) -> Optional[Lead]:
        """
        Retrieve a lead by ID.
        
        Returns:
            Lead object or None
        """
        try:
            result = self.client.table(self.table_name).select('*').eq('lead_id', lead_id).execute()
            
            if result.data and len(result.data) > 0:
                return Lead.from_dict(result.data[0])
            return None
            
        except Exception as e:
            print(f"Error retrieving lead: {e}")
            return None
    
    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a lead's information.
        
        Returns:
            bool indicating success
        """
        try:
            result = self.client.table(self.table_name).update(updates).eq('lead_id', lead_id).execute()
            return result.data is not None
            
        except Exception as e:
            print(f"Error updating lead: {e}")
            return False
    
    def update_lead_status(self, lead_id: str, status: str) -> bool:
        """Update lead status"""
        return self.update_lead(lead_id, {'status': status})
    
    def get_leads_by_status(self, status: str, business_id: Optional[str] = None, limit: int = 100) -> List[Lead]:
        """
        Get leads filtered by status (and optionally by business).
        
        Returns:
            List of Lead objects
        """
        try:
            query = self.client.table(self.table_name)\
                .select('*')\
                .eq('status', status)
            
            if business_id:
                query = query.eq('business_id', business_id)
            
            result = query.order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return [Lead.from_dict(lead_data) for lead_data in result.data]
            
        except Exception as e:
            print(f"Error retrieving leads: {e}")
            return []
    
    def get_all_leads(self, business_id: Optional[str] = None, limit: int = 100) -> List[Lead]:
        """
        Get all leads (optionally filtered by business).
        
        Returns:
            List of Lead objects
        """
        try:
            query = self.client.table(self.table_name).select('*')
            
            if business_id:
                query = query.eq('business_id', business_id)
            
            result = query.order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return [Lead.from_dict(lead_data) for lead_data in result.data]
            
        except Exception as e:
            print(f"Error retrieving all leads: {e}")
            return []
    
    def get_qualified_leads(self, min_score: int = 60, business_id: Optional[str] = None) -> List[Lead]:
        """
        Get leads that meet qualification threshold (optionally filtered by business).
        
        Returns:
            List of qualified Lead objects
        """
        try:
            query = self.client.table(self.table_name)\
                .select('*')\
                .gte('qualification_score', min_score)
            
            if business_id:
                query = query.eq('business_id', business_id)
            
            result = query.order('qualification_score', desc=True)\
                .limit(100)\
                .execute()
            
            return [Lead.from_dict(lead_data) for lead_data in result.data]
            
        except Exception as e:
            print(f"Error retrieving qualified leads: {e}")
            return []
