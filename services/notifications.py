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


def _password_reset_email_html(reset_url: str) -> str:
    """Build branded HTML for password reset email with the link as an explicit <a> tag and as plain text."""
    import html
    if not reset_url or not reset_url.startswith("http"):
        reset_url = ""
    safe_url = html.escape(reset_url, quote=True)
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://lumo22.com"
    logo_url = f"{base}/static/images/logo.png"
    # Show link as both clickable and as plain text so it's visible even if client strips links
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lumo 22 – Reset password</title>
</head>
<body style="margin:0; padding:0; background:#f6f6f4; font-family: {BRAND_FONT}; font-size: 16px; line-height: 1.7; color: {BRAND_TEXT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f4;">
    <tr>
      <td style="padding: 32px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden;">
          <tr>
            <td style="padding: 40px 32px 32px;">
              <p style="margin:0 0 24px; font-size: 14px; letter-spacing: 0.2em; text-transform: uppercase; color: {BRAND_GOLD}; font-weight: 600;">Lumo 22</p>
              <p style="margin:0 0 16px;">Hi,</p>
              <p style="margin:0 0 16px;">You requested a password reset for your Lumo 22 account.</p>
              <p style="margin:0 0 12px;">Click the link below to set a new password (link expires in 1 hour):</p>
              <p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:12px 24px; background:#000; color:#fff; text-decoration:none; border-radius:8px; font-weight:600;">Reset my password</a></p>
              <p style="margin:0 0 8px; font-size:14px; color:#666;">Or copy and paste this link into your browser:</p>
              <p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
              <p style="margin:0 0 16px;">If you didn't request this, you can ignore this email. Your password will stay the same.</p>
              <p style="margin:0;">— Lumo 22</p>
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


def _login_link_email_html(account_url: str) -> str:
    """Build branded HTML for login link email with the link as an explicit <a> tag and plain text."""
    import html
    if not account_url or not account_url.startswith("http"):
        account_url = ""
    safe_url = html.escape(account_url, quote=True)
    base = (Config.BASE_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        base = "https://lumo22.com"
    logo_url = f"{base}/static/images/logo.png"
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Lumo 22 – Login link</title></head>
<body style="margin:0; padding:0; background:#f6f6f4; font-family: {BRAND_FONT}; font-size: 16px; line-height: 1.7; color: {BRAND_TEXT};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f4;">
    <tr><td style="padding: 32px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden;">
          <tr><td style="padding: 40px 32px 32px;">
              <p style="margin:0 0 24px; font-size: 14px; letter-spacing: 0.2em; text-transform: uppercase; color: {BRAND_GOLD}; font-weight: 600;">Lumo 22</p>
              <p style="margin:0 0 16px;">Click the link below to open your account (link works once, expires in 2 minutes):</p>
              <p style="margin:0 0 24px;"><a href="{safe_url}" style="display:inline-block; padding:12px 24px; background:#000; color:#fff; text-decoration:none; border-radius:8px; font-weight:600;">Open my account</a></p>
              <p style="margin:0 0 8px; font-size:14px; color:#666;">Or copy and paste this link into your browser:</p>
              <p style="margin:0 0 24px; font-size:13px; word-break:break-all; color:#333;">{safe_url}</p>
              <p style="margin:0;">— Lumo 22</p>
            </td></tr>
          <tr><td style="padding: 24px 32px 32px; border-top: 1px solid #e5e5e5; font-size: 13px; color: {BRAND_MUTED};">
              <p style="margin:0 0 12px;"><img src="{logo_url}" alt="Lumo 22" width="120" height="auto" style="display:block; height:auto; max-width:120px;" /></p>
              <p style="margin:0;">Lumo 22 · <a href="mailto:hello@lumo22.com" style="color:{BRAND_GOLD}; text-decoration:none;">hello@lumo22.com</a></p>
              <p style="margin:8px 0 0;">Lighting the way to better business</p>
            </td></tr>
        </table>
      </td></tr>
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

    def send_password_reset_email(self, to_email: str, reset_url: str) -> bool:
        """Send password reset email with plain and HTML body; link is explicit in HTML so it always appears."""
        if not reset_url or not reset_url.startswith("http"):
            print(f"[SendGrid] Password reset NOT sent: invalid reset_url (empty or not http)")
            return False
        subject = "Reset your Lumo 22 password"
        body = f"""Hi,

You requested a password reset for your Lumo 22 account.

Click the link below to set a new password (link expires in 1 hour):

{reset_url}

If the link doesn't work, copy and paste the link above into your browser.

If you didn't request this, you can ignore this email. Your password will stay the same.

— Lumo 22
"""
        html_body = _password_reset_email_html(reset_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

    def send_login_link_email(self, to_email: str, account_url: str) -> bool:
        """Send login link email with plain and HTML body; link is explicit in HTML so it always appears."""
        if not account_url or not account_url.startswith("http"):
            print("[SendGrid] Login link NOT sent: invalid account_url (empty or not http)")
            return False
        subject = "Your Lumo 22 login link"
        body = f"""Click the link below to open your account (link works once, expires in 2 minutes):

{account_url}

If the link doesn't work, copy and paste the link above into your browser.

— Lumo 22
"""
        html_body = _login_link_email_html(account_url)
        return self.send_email(to_email, subject, body, html_body=html_body)

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
            status = getattr(response, "status_code", None)
            ok = status in [200, 201, 202]
            if ok:
                print(f"[SendGrid] Email sent OK (status={status}): to={to_email} subject={subject!r}")
            else:
                body_preview = getattr(response, "body", "") or ""
                if isinstance(body_preview, bytes):
                    body_preview = body_preview.decode("utf-8", errors="replace")[:300]
                else:
                    body_preview = str(body_preview)[:300]
                print(f"[SendGrid] Email rejected (status={status}): to={to_email} subject={subject!r} body={body_preview}")
            return ok
        except Exception as e:
            import traceback
            print(f"[SendGrid] Error sending email to {to_email}: {e}")
            traceback.print_exc()
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
        extra_attachments: Optional[list] = None,
    ) -> tuple:
        """Send email with one or more attachments. Returns (True, None) on success, (False, error_message) on failure.
        extra_attachments: optional list of {"filename": str, "content": bytes, "mime_type": str} for additional files."""
        to_email = _sanitize_email_value(to_email or "")
        if not to_email or "@" not in to_email:
            msg = "Invalid or missing recipient email"
            print(f"[SendGrid] Email with attachment NOT sent (invalid to_email): subject={subject!r}")
            return (False, msg)
        if not self.sendgrid_client:
            msg = "SendGrid not configured (missing SENDGRID_API_KEY)"
            print(f"[SendGrid] Email with attachment NOT sent (no API key): subject={subject!r} to={to_email}")
            return (False, msg)

        def b64_for(data: bytes) -> str:
            return base64.b64encode(data).decode("ascii")

        attachments_to_add = []
        if file_content_bytes is not None:
            attachments_to_add.append((filename, b64_for(file_content_bytes), mime_type))
        elif file_content is not None:
            attachments_to_add.append((filename, b64_for(file_content.encode("utf-8")), mime_type))

        for extra in (extra_attachments or []):
            fn = extra.get("filename")
            content = extra.get("content")
            mt = extra.get("mime_type", "application/octet-stream")
            if fn and content is not None:
                attachments_to_add.append((fn, b64_for(content), mt))

        if not attachments_to_add:
            msg = "No attachment content (need file_content/file_content_bytes or extra_attachments)"
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
            attachment_list = []
            for fn, enc, mt in attachments_to_add:
                att = Attachment(
                    file_content=FileContent(enc),
                    file_name=FileName(fn),
                    file_type=FileType(mt),
                )
                attachment_list.append(att)
            message.attachment = attachment_list
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
