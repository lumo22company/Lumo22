"""
Outreach automation service for contacting service businesses.
Handles email sequences, LinkedIn outreach, and follow-ups.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

class OutreachService:
    """Service for automated outreach to prospects"""
    
    def __init__(self):
        self.email_templates = self._load_email_templates()
    
    def create_outreach_sequence(
        self,
        prospect: Dict[str, Any],
        channel: str = 'email'
    ) -> Dict[str, Any]:
        """
        Create an outreach sequence for a prospect.
        
        Args:
            prospect: Prospect business information
            channel: 'email' or 'linkedin'
        
        Returns:
            Outreach sequence configuration
        """
        sequence = {
            'prospect_id': prospect.get('id'),
            'channel': channel,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'messages': []
        }
        
        # Create message sequence
        if channel == 'email':
            sequence['messages'] = self._create_email_sequence(prospect)
        elif channel == 'linkedin':
            sequence['messages'] = self._create_linkedin_sequence(prospect)
        
        return sequence
    
    def _create_email_sequence(self, prospect: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create email sequence"""
        messages = [
            {
                'step': 1,
                'type': 'initial',
                'template': 'initial_outreach',
                'subject': self._get_subject_line(prospect),
                'body': self._render_template('initial_outreach', prospect),
                'send_delay_days': 0,
                'status': 'pending'
            },
            {
                'step': 2,
                'type': 'follow_up',
                'template': 'follow_up_1',
                'subject': 'Quick follow-up - Automated lead system',
                'body': self._render_template('follow_up_1', prospect),
                'send_delay_days': 3,
                'status': 'pending'
            },
            {
                'step': 3,
                'type': 'follow_up',
                'template': 'follow_up_2',
                'subject': 'Last chance - Free trial available',
                'body': self._render_template('follow_up_2', prospect),
                'send_delay_days': 7,
                'status': 'pending'
            }
        ]
        
        return messages
    
    def _create_linkedin_sequence(self, prospect: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create LinkedIn message sequence"""
        messages = [
            {
                'step': 1,
                'type': 'connection_request',
                'message': self._render_template('linkedin_connection', prospect),
                'send_delay_days': 0,
                'status': 'pending'
            },
            {
                'step': 2,
                'type': 'message',
                'message': self._render_template('linkedin_follow_up', prospect),
                'send_delay_days': 2,
                'status': 'pending'
            }
        ]
        
        return messages
    
    def _load_email_templates(self) -> Dict[str, str]:
        """Load email templates"""
        return {
            'initial_outreach': """Hi {name},

I noticed {business_name} offers {service_type} services. 

I help service businesses like yours automate lead capture, qualification, and booking - so you get consistent enquiries without spending time chasing customers.

Quick question: Are you currently spending time manually following up with leads?

If yes, I'd love to show you how we've automated this for similar businesses. 

We offer a free trial - no commitment required.

Would you be open to a quick 15-minute demo?

Best,
Sophie
Lumo22""",
            
            'follow_up_1': """Hi {name},

Just following up on my previous email about automating your lead process.

I know you're busy, so here's the quick version:

✅ AI automatically qualifies every lead (0-100 score)
✅ Auto-generates booking links for qualified leads  
✅ Saves everything to your database
✅ Sends automated follow-ups

Result: More booked appointments, less manual work.

Free trial available - interested?

Best,
Sophie""",
            
            'follow_up_2': """Hi {name},

Last follow-up - I promise!

I'm reaching out because I genuinely think our automated lead system could save you hours each week.

We're offering a free trial to a few select service businesses this month.

Would you like to be one of them?

Just reply "yes" and I'll set it up.

Best,
Sophie
Lumo22""",
            
            'linkedin_connection': """Hi {name}, I help service businesses automate lead capture and booking. Would love to connect!""",
            
            'linkedin_follow_up': """Hi {name}, Thanks for connecting! I noticed {business_name} offers {service_type}. I help similar businesses automate their lead process - would you be open to a quick chat?"""
        }
    
    def _render_template(self, template_name: str, prospect: Dict[str, Any]) -> str:
        """Render email template with prospect data"""
        template = self.email_templates.get(template_name, '')
        
        # Fill in template variables
        return template.format(
            name=prospect.get('contact_name', 'there'),
            business_name=prospect.get('name', 'your business'),
            service_type=prospect.get('service_type', 'services'),
            location=prospect.get('location', 'your area')
        )
    
    def _get_subject_line(self, prospect: Dict[str, Any]) -> str:
        """Generate personalized subject line"""
        subjects = [
            f"Automate {prospect.get('service_type', 'your')} lead capture?",
            f"Stop chasing leads - automate instead",
            f"Free trial: AI-powered lead system for {prospect.get('name', 'service businesses')}",
            f"Turn interest into booked appointments automatically"
        ]
        
        # Use first one for now (could randomize)
        return subjects[0]
    
    def schedule_outreach(
        self,
        prospect: Dict[str, Any],
        channel: str = 'email'
    ) -> Dict[str, Any]:
        """
        Schedule outreach for a prospect.
        
        Returns:
            Scheduled outreach configuration
        """
        sequence = self.create_outreach_sequence(prospect, channel)
        
        # Calculate send times
        base_time = datetime.utcnow()
        for message in sequence['messages']:
            send_time = base_time + timedelta(days=message['send_delay_days'])
            message['scheduled_for'] = send_time.isoformat()
        
        return sequence
