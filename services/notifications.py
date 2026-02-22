"""
Notification service for emails and SMS.
Handles automated follow-ups and booking confirmations.
Uses Lumo 22 brand (BRAND_STYLE_GUIDE): black, gold accent, Century Gothic.
"""
import os
import re
from typing import Dict, Any, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Attachment, FileContent, FileName, FileType
import base64
from twilio.rest import Client as TwilioClient
from config import Config

# Brand (from BRAND_STYLE_GUIDE.md)
BRAND_BLACK = "#000000"
BRAND_GOLD = "#fff200"
BRAND_TEXT = "#000000"
BRAND_MUTED = "#9a9a96"
BRAND_FONT = "Century Gothic, CenturyGothic, Apple Gothic, sans-serif"


def _branded_html_email(body_plain: str) -> str:
    """Wrap plain body in Lumo 22 branded HTML (black, gold accent, footer)."""
    import html
    body_plain = (body_plain or "").strip()
    # Escape HTML and linkify URLs
    lines = body_plain.split("\n")
    escaped_lines = []
    for line in lines:
        line = html.escape(line)
        # Simple linkify: http(s)://... patterns
        line = re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" style="color:' + BRAND_GOLD + "; text-decoration: none; border-bottom: 1px solid " + BRAND_GOLD + ';">\1</a>',
            line,
        )
        escaped_lines.append(line)
    body_html = "<br>\n".join(escaped_lines)
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://lumo22.com"
    logo_url = f"{base}/static/images/logo.png"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lumo 22</title>
</head>
<body style="margin:0; padding:0; background:#f6f6f4; font-family: {BRAND_FONT}; font-size: 16px; line-height: 1.7; color: {BRAND_TEXT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f4;">
    <tr>
      <td style="padding: 32px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden;">
          <tr>
            <td style="padding: 40px 32px 32px;">
              <p style="margin:0 0 24px; font-size: 14px; letter-spacing: 0.2em; text-transform: uppercase; color: {BRAND_GOLD}; font-weight: 600;">Lumo 22</p>
              <div style="color: {BRAND_TEXT};">
                {body_html}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 24px 32px 32px; border-top: 1px solid #e5e5e5; font-size: 13px; color: {BRAND_MUTED};">
              <p style="margin:0 0 12px;"><img src="{logo_url}" alt="Lumo 22" width="120" height="auto" style="display:block; height:auto; max-width:120px;" /></p>
              <p style="margin:0;">Lumo 22 · <a href="mailto:hello@lumo22.com" style="color:{BRAND_GOLD}; text-decoration:none;">hello@lumo22.com</a></p>
              <p style="margin:8px 0 0;">Lighting the way to better business</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _sanitize_email_value(s: str) -> str:
    """Remove control chars so SendGrid doesn't raise 'Invalid non-printable ASCII'."""
    if not s or not isinstance(s, str):
        return (s or "").strip()
    return re.sub(r"[\x00-\x1f\x7f]", "", s.strip())

class NotificationService:
    """Service for sending emails and SMS notifications"""
    
    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        
        api_key = (Config.SENDGRID_API_KEY or "").strip()
        api_key = re.sub(r"[\x00-\x1f\x7f]", "", api_key)
        if api_key:
            self.sendgrid_client = SendGridAPIClient(api_key=api_key)
        
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
        to_email = _sanitize_email_value(to_email or "")
        if not to_email or "@" not in to_email:
            print(f"[SendGrid] Email NOT sent (invalid to_email): subject={subject!r}")
            return False
        if not self.sendgrid_client:
            print(f"[SendGrid] Email NOT sent (no API key): subject={subject!r} to={to_email}")
            return False

        try:
            from_addr = _sanitize_email_value(Config.FROM_EMAIL or "") or "noreply@lumo22.com"
            from_name = (Config.FROM_NAME or "Lumo 22").strip() or "Lumo 22"
            html_content = html_body if html_body is not None else _branded_html_email(body)
            message = Mail(
                from_email=Email(from_addr, from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html_content
            )
            response = self.sendgrid_client.send(message)
            ok = response.status_code in [200, 201, 202]
            if ok:
                print(f"[SendGrid] Email sent OK (status={response.status_code}): to={to_email} subject={subject!r}")
            else:
                print(f"[SendGrid] Email rejected (status={response.status_code}): to={to_email} subject={subject!r} body={getattr(response, 'body', '')[:200]}")
            return ok
        except Exception as e:
            print(f"[SendGrid] Error sending email to {to_email}: {e}")
            return False

    def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        filename: str,
        file_content: Optional[str] = None,
        file_content_bytes: Optional[bytes] = None,
        mime_type: str = "text/plain",
    ) -> tuple:
        """Send email with a single attachment. Returns (True, None) on success, (False, error_message) on failure."""
        to_email = _sanitize_email_value(to_email or "")
        if not to_email or "@" not in to_email:
            msg = "Invalid or missing recipient email"
            print(f"[SendGrid] Email with attachment NOT sent (invalid to_email): subject={subject!r}")
            return (False, msg)
        if not self.sendgrid_client:
            msg = "SendGrid not configured (missing SENDGRID_API_KEY)"
            print(f"[SendGrid] Email with attachment NOT sent (no API key): subject={subject!r} to={to_email}")
            return (False, msg)
        if file_content_bytes is not None:
            encoded = base64.b64encode(file_content_bytes).decode("ascii")
        elif file_content is not None:
            encoded = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
        else:
            msg = "No attachment content (need file_content or file_content_bytes)"
            print("[SendGrid] send_email_with_attachment: " + msg)
            return (False, msg)
        try:
            from_addr = _sanitize_email_value(Config.FROM_EMAIL or "") or "noreply@lumo22.com"
            from_name = (Config.FROM_NAME or "Lumo 22").strip() or "Lumo 22"
            html_content = _branded_html_email(body)
            message = Mail(
                from_email=Email(from_addr, from_name),
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html_content,
            )
            attachment = Attachment(
                file_content=FileContent(encoded),
                file_name=FileName(filename),
                file_type=FileType(mime_type),
            )
            message.attachment = attachment
            response = self.sendgrid_client.send(message)
            ok = response.status_code in [200, 201, 202]
            if ok:
                print(f"[SendGrid] Email with attachment sent OK (status={response.status_code}): to={to_email} subject={subject!r}")
                return (True, None)
            body_preview = (getattr(response, "body", None) or b"").decode("utf-8", errors="replace")[:300]
            msg = f"SendGrid rejected (status {response.status_code}): {body_preview}"
            print(f"[SendGrid] Email with attachment rejected (status={response.status_code}): to={to_email} body={body_preview}")
            return (False, msg)
        except Exception as e:
            msg = str(e) or repr(e)
            print(f"[SendGrid] Error sending email with attachment to {to_email}: {e}")
            return (False, msg)
    
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
