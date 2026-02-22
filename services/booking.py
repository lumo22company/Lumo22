"""
Automated booking service using Calendly API.
Creates booking links and manages appointments.

When you add an endpoint that returns available appointment slots (e.g. from Calendly
or a calendar), use services.availability.filter_slots_tight_scheduling with the
front_desk_setup's tight_scheduling_enabled and minimum_gap_between_appointments:
if enabled, only show slots within that many minutes of existing same-day bookings;
if no bookings that day, show all slots. If tight scheduling is off, show all slots.
"""
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from config import Config

class BookingService:
    """Service for automated appointment booking"""
    
    def __init__(self):
        self.api_key = Config.CALENDLY_API_KEY
        self.event_type_id = Config.CALENDLY_EVENT_TYPE_ID
        self.base_url = Config.CALENDLY_BASE_URL
    
    def create_booking_link(
        self,
        lead_email: str,
        lead_name: str,
        service_type: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Calendly scheduling link for a lead.
        
        Returns:
            dict with booking_link and event_id
        """
        
        if not self.api_key or not self.event_type_id:
            # Return a placeholder booking link if Calendly not configured
            return {
                'booking_link': f"mailto:{Config.FROM_EMAIL}?subject=Booking Request: {service_type}",
                'event_id': None,
                'method': 'email_fallback'
            }
        
        try:
            # Calendly API endpoint for creating one-time scheduling links
            # Note: Calendly API v2 requires OAuth, so we'll use a simpler approach
            # with pre-configured event types and direct links
            
            # For MVP, we'll generate a direct Calendly link
            # In production, you'd use the Calendly API with OAuth
            calendly_url = f"https://calendly.com/{self._extract_calendly_username()}/{self._get_event_slug()}"
            
            # Add pre-fill parameters
            booking_link = f"{calendly_url}?name={lead_name.replace(' ', '+')}&email={lead_email}"
            
            if notes:
                booking_link += f"&notes={notes.replace(' ', '+')}"
            
            return {
                'booking_link': booking_link,
                'event_id': None,
                'method': 'calendly_direct'
            }
            
        except Exception as e:
            print(f"Booking service error: {e}")
            # Fallback to email
            return {
                'booking_link': f"mailto:{Config.FROM_EMAIL}?subject=Booking Request: {service_type}&body=From: {lead_name} ({lead_email})",
                'event_id': None,
                'method': 'email_fallback'
            }
    
    def _extract_calendly_username(self) -> str:
        """Extract Calendly username from event type ID or config"""
        # If event_type_id is a full URL, extract username
        if '/' in str(self.event_type_id):
            parts = str(self.event_type_id).split('/')
            return parts[-2] if len(parts) > 1 else 'your-username'
        return 'your-username'  # Replace with your Calendly username
    
    def _get_event_slug(self) -> str:
        """Get event type slug"""
        # Extract from event_type_id or use default
        if '/' in str(self.event_type_id):
            parts = str(self.event_type_id).split('/')
            return parts[-1] if parts else 'consultation'
        return 'consultation'  # Default event type
    
    def send_booking_invitation(
        self,
        lead_email: str,
        lead_name: str,
        booking_link: str,
        service_type: str
    ) -> bool:
        """
        Send booking invitation to lead.
        This would typically integrate with email service.
        Returns True if successful.
        """
        # This will be handled by the notification service
        # Just return success for now
        return True
