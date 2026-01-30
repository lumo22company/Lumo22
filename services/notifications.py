"""
Notification service for emails and SMS.
Handles automated follow-ups and booking confirmations.
"""
import os
from typing import Dict, Any, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType
import base64
from twilio.rest import Client as TwilioClient
from config import Config

class NotificationService:
    """Service for sending emails and SMS notifications"""
    
    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        
        if Config.SENDGRID_API_KEY:
            self.sendgrid_client = SendGridAPIClient(api_key=Config.SENDGRID_API_KEY)
        
        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN:
            self.twilio_client = TwilioClient(
                Config.TWILIO_ACCOUNT_SID,
                Config.TWILIO_AUTH_TOKEN
            )
    
    def send_lead_notification(
        self,
        lead_email: str,
        lead_name: str,
        service_type: str,
        booking_link: Optional[str] = None
    ) -> bool:
        """
        Send notification to lead with booking information.
        
        Returns:
            bool indicating success
        """
        subject = f"Thank you for your interest in {service_type}"
        
        if booking_link:
            body = f"""
Hi {lead_name},

Thank you for your interest in our {service_type} services!

We'd love to schedule a time to discuss your needs. Please book a convenient time using the link below:

{booking_link}

If you have any questions, feel free to reply to this email.

Best regards,
{Config.BUSINESS_NAME}
"""
        else:
            body = f"""
Hi {lead_name},

Thank you for your interest in our {service_type} services!

We'll be in touch shortly to discuss your needs.

Best regards,
{Config.BUSINESS_NAME}
"""
        
        return self.send_email(lead_email, subject, body)
    
    def send_internal_notification(
        self,
        admin_email: str,
        lead_name: str,
        lead_email: str,
        service_type: str,
        qualification_score: int,
        booking_link: Optional[str] = None
    ) -> bool:
        """
        Send internal notification to business owner about new lead.
        
        Returns:
            bool indicating success
        """
        subject = f"New Lead: {lead_name} - {service_type} (Score: {qualification_score})"
        
        body = f"""
New Lead Received:

Name: {lead_name}
Email: {lead_email}
Service: {service_type}
Qualification Score: {qualification_score}/100

{f'Booking Link: {booking_link}' if booking_link else 'No booking link generated'}

---
This is an automated notification from your lead capture system.
"""
        
        return self.send_email(admin_email, subject, body)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email using SendGrid.
        
        Returns:
            bool indicating success
        """
        if not self.sendgrid_client:
            print(f"Email not sent (SendGrid not configured): {subject} to {to_email}")
            return False
        
        try:
            message = Mail(
                from_email=Config.FROM_EMAIL,
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html_body or body.replace('\n', '<br>')
            )
            
            response = self.sendgrid_client.send(message)
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        filename: str,
        file_content: str,
        mime_type: str = "text/plain",
    ) -> bool:
        """Send email with a single attachment (e.g. markdown file). file_content is raw string."""
        if not self.sendgrid_client:
            print(f"Email not sent (SendGrid not configured): {subject} to {to_email}")
            return False
        try:
            message = Mail(
                from_email=Config.FROM_EMAIL,
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=body.replace("\n", "<br>"),
            )
            encoded = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
            attachment = Attachment(
                file_content=FileContent(encoded),
                file_name=FileName(filename),
                file_type=FileType(mime_type),
            )
            message.attachment = attachment
            response = self.sendgrid_client.send(message)
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"Error sending email with attachment: {e}")
            return False
    
    def send_sms(
        self,
        to_phone: str,
        message: str
    ) -> bool:
        """
        Send SMS using Twilio.
        
        Returns:
            bool indicating success
        """
        if not self.twilio_client or not Config.TWILIO_PHONE_NUMBER:
            print(f"SMS not sent (Twilio not configured): {message} to {to_phone}")
            return False
        
        try:
            message = self.twilio_client.messages.create(
                body=message,
                from_=Config.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            return message.sid is not None
            
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False
