# AI-Powered Lead Capture, Qualification & Booking System

An automated system that captures leads, qualifies them using AI, and books appointments automatically for service businesses.

## 🎯 System Overview

This system provides:
- **Lead Capture**: Multiple channels (web forms, chatbots, API)
- **AI Qualification**: Automatic lead scoring and qualification using OpenAI
- **Auto-Booking**: Direct calendar integration for appointment scheduling
- **CRM Integration**: Track leads through the entire funnel
- **Automation**: Automated follow-ups and notifications

## 💰 Cost Breakdown (Low-Cost Stack)

| Component | Tool | Cost | Notes |
|-----------|------|------|-------|
| Backend | Python/Flask (self-hosted) | Free | Can deploy on Railway/Render free tier |
| AI Qualification | OpenAI API | ~$0.01-0.05/lead | Pay-per-use, very affordable |
| Database | Supabase (PostgreSQL) | Free tier | 500MB free, perfect for MVP |
| Calendar Booking | Calendly API | Free tier | Up to 1 event type free |
| Email | SendGrid | Free tier | 100 emails/day free |
| SMS | Twilio | $0.0075/SMS | Pay-per-use |
| Forms | Built-in Flask | Free | No external service needed |
| Hosting | Railway/Render | Free tier | 500 hours/month free |

**Total Monthly Cost: ~$10-50** (depending on volume)

## 🏗️ Architecture

```
Lead Sources → Capture System → AI Qualification → Booking Engine → CRM → Notifications
     ↓              ↓                    ↓              ↓            ↓         ↓
  Forms/API    Flask Backend      OpenAI API    Calendly API   Supabase   Email/SMS
```

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Initialize database:**
   ```bash
   python init_db.py
   ```

4. **Run the server:**
   ```bash
   python app.py
   ```

5. **Access the system:**
   - Web interface: http://localhost:5000
   - API docs: http://localhost:5000/api/docs

## 📁 Project Structure

```
LUMO22/
├── app.py                 # Main Flask application
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── init_db.py            # Database initialization
├── README.md             # This file
├── api/
│   ├── __init__.py
│   ├── routes.py         # API endpoints
│   └── webhooks.py       # Webhook handlers
├── services/
│   ├── __init__.py
│   ├── ai_qualifier.py   # AI qualification engine
│   ├── booking.py        # Calendar booking service
│   ├── notifications.py  # Email/SMS notifications
│   └── crm.py            # CRM integration
├── models/
│   ├── __init__.py
│   └── lead.py           # Lead data models
├── templates/
│   ├── index.html        # Lead capture form
│   ├── dashboard.html    # Admin dashboard
│   └── webhook.html      # Webhook test page
└── static/
    └── css/
        └── style.css     # Styling
```

## 🔧 Configuration

### Required API Keys

1. **OpenAI API Key** (for AI qualification)
   - Get from: https://platform.openai.com/api-keys
   - Cost: ~$0.01-0.05 per lead qualification

2. **Supabase** (database)
   - Get from: https://supabase.com
   - Free tier includes 500MB storage

3. **Calendly** (optional, for booking)
   - Get from: https://calendly.com/integrations/api
   - Free tier available

4. **SendGrid** (optional, for emails)
   - Get from: https://sendgrid.com
   - Free tier: 100 emails/day

5. **Twilio** (optional, for SMS)
   - Get from: https://www.twilio.com
   - Pay-per-use pricing

## 📊 Features

### 1. Lead Capture
- Web form with validation
- API endpoint for external integrations
- Webhook support for third-party forms
- Chatbot integration ready

### 2. AI Qualification
- Automatic lead scoring (0-100)
- Qualification criteria analysis
- Budget estimation
- Urgency detection
- Service type matching

### 3. Auto-Booking
- Direct calendar integration
- Automatic appointment scheduling
- Timezone handling
- Reminder notifications

### 4. CRM Features
- Lead tracking and status
- Conversion analytics
- Customer history
- Automated follow-ups

## 🔒 Security & Compliance

- GDPR compliant data handling
- Secure API key management
- Rate limiting on endpoints
- Input validation and sanitization
- HTTPS ready (use in production)

## 📈 Scaling

The system is designed to scale:
- Start with free tiers
- Upgrade as volume increases
- Can handle 1000+ leads/month on free tier
- Scales to 10,000+ leads/month with paid tiers

## 🆘 Support

For issues or questions, check the documentation in each module or review the code comments.
