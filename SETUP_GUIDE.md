# Setup Guide: AI-Powered Lead Capture & Booking System

This guide will walk you through setting up your automated lead capture, qualification, and booking system step-by-step.

## Prerequisites

- Python 3.8 or higher
- A Supabase account (free tier)
- An OpenAI API key
- (Optional) Calendly account for booking
- (Optional) SendGrid account for emails
- (Optional) Twilio account for SMS

## Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Set Up Supabase Database

1. **Create a Supabase account:**
   - Go to https://supabase.com
   - Sign up for free (500MB storage, perfect for MVP)

2. **Create a new project:**
   - Click "New Project"
   - Choose a name and database password
   - Select a region close to you

3. **Create the leads table:**
   - Go to SQL Editor in your Supabase dashboard
   - Run this SQL:

```sql
CREATE TABLE IF NOT EXISTS leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    service_type TEXT NOT NULL,
    message TEXT NOT NULL,
    source TEXT DEFAULT 'web_form',
    qualification_score INTEGER,
    status TEXT DEFAULT 'new',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    booked_at TIMESTAMPTZ,
    booking_link TEXT,
    qualification_details JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_qualification_score ON leads(qualification_score);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
```

4. **Get your Supabase credentials:**
   - Go to Project Settings → API
   - Copy your "Project URL" (SUPABASE_URL)
   - Copy your "anon public" key (SUPABASE_KEY)

## Step 3: Set Up OpenAI API

1. **Create an OpenAI account:**
   - Go to https://platform.openai.com
   - Sign up or log in

2. **Get your API key:**
   - Go to API Keys section
   - Click "Create new secret key"
   - Copy the key (starts with `sk-`)

3. **Add credits:**
   - Add at least $5-10 in credits
   - Cost per lead qualification: ~$0.01-0.05
   - $10 = ~200-1000 lead qualifications

## Step 4: Configure Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   # Required
   OPENAI_API_KEY=sk-your-key-here
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-supabase-key-here
   
   # Optional but recommended
   SECRET_KEY=generate-a-random-secret-key-here
   FROM_EMAIL=your-email@yourdomain.com
   BUSINESS_NAME=Your Business Name
   ```

## Step 5: (Optional) Set Up Calendly for Booking

1. **Create a Calendly account:**
   - Go to https://calendly.com
   - Sign up for free

2. **Create an event type:**
   - Create a consultation/meeting event type
   - Note the event type URL (e.g., `your-username/consultation`)

3. **Get API access:**
   - Go to Integrations → API & Webhooks
   - Create a personal access token
   - Add to `.env`:
     ```
     CALENDLY_API_KEY=your-token-here
     CALENDLY_EVENT_TYPE_ID=your-username/consultation
     ```

## Step 6: (Optional) Set Up SendGrid for Emails

1. **Create a SendGrid account:**
   - Go to https://sendgrid.com
   - Sign up (free tier: 100 emails/day)

2. **Verify your sender:**
   - Go to Settings → Sender Authentication
   - Verify a single sender email

3. **Get API key:**
   - Go to Settings → API Keys
   - Create API key with "Mail Send" permissions
   - Add to `.env`:
     ```
     SENDGRID_API_KEY=SG.your-key-here
     FROM_EMAIL=your-verified-email@yourdomain.com
     ```

## Step 7: (Optional) Set Up Twilio for SMS

1. **Create a Twilio account:**
   - Go to https://www.twilio.com
   - Sign up (free trial available)

2. **Get a phone number:**
   - Get a trial phone number (free)

3. **Get credentials:**
   - Account SID and Auth Token from dashboard
   - Add to `.env`:
     ```
     TWILIO_ACCOUNT_SID=your-account-sid
     TWILIO_AUTH_TOKEN=your-auth-token
     TWILIO_PHONE_NUMBER=+1234567890
     ```

## Step 8: Initialize Database

```bash
python init_db.py
```

This will verify your database connection and provide instructions if needed.

## Step 9: Run the Application

```bash
python app.py
```

The server will start on http://localhost:5000

## Step 10: Test the System

1. **Test the lead capture form:**
   - Go to http://localhost:5000
   - Fill out the form and submit
   - Check that you receive notifications

2. **Test the API:**
   ```bash
   curl -X POST http://localhost:5000/api/capture \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Lead",
       "email": "test@example.com",
       "phone": "+1234567890",
       "service_type": "Consultation",
       "message": "I need help with my project"
     }'
   ```

3. **View the dashboard:**
   - Go to http://localhost:5000/dashboard
   - See all captured leads

## Step 11: Deploy to Production

### Option 1: Railway (Recommended - Free Tier)

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. **Deploy:**
   ```bash
   railway init
   railway up
   ```

3. **Set environment variables:**
   - Go to Railway dashboard
   - Add all variables from your `.env` file

### Option 2: Render (Free Tier)

1. **Connect your GitHub repo**
2. **Create a new Web Service**
3. **Set build command:** `pip install -r requirements.txt`
4. **Set start command:** `gunicorn app:app`
5. **Add environment variables**

### Option 3: Heroku

1. **Install Heroku CLI**
2. **Create app:**
   ```bash
   heroku create your-app-name
   ```
3. **Set environment variables:**
   ```bash
   heroku config:set OPENAI_API_KEY=your-key
   # ... etc
   ```
4. **Deploy:**
   ```bash
   git push heroku main
   ```

## Integration Examples

### Typeform Integration

1. Create your Typeform
2. Go to Connect → Webhooks
3. Add webhook URL: `https://your-domain.com/webhooks/typeform`
4. Map form fields to lead fields

### Zapier Integration

1. Create a Zap
2. Trigger: Your form/CRM/etc
3. Action: Webhooks by Zapier
4. URL: `https://your-domain.com/webhooks/zapier`
5. Method: POST
6. Data: Map to lead fields

### Make.com Integration

1. Create a scenario
2. Trigger: Your data source
3. HTTP module: POST to `https://your-domain.com/webhooks/generic`
4. Map fields

## Cost Breakdown (Monthly)

| Service | Free Tier | Paid Tier (if needed) |
|---------|-----------|----------------------|
| Supabase | 500MB storage | $25/month for 8GB |
| OpenAI | Pay-per-use | ~$0.01-0.05/lead |
| Calendly | 1 event type | $10/month for unlimited |
| SendGrid | 100 emails/day | $15/month for 50k |
| Twilio | Trial credits | ~$0.0075/SMS |
| Hosting | Railway/Render free | $7-20/month |

**Total for MVP: ~$0-10/month**
**Total for scaling: ~$50-100/month**

## Troubleshooting

### "OpenAI API key not configured"
- Check your `.env` file has `OPENAI_API_KEY=sk-...`
- Make sure you're running from the project directory

### "Supabase connection failed"
- Verify your SUPABASE_URL and SUPABASE_KEY
- Check that the leads table exists
- Ensure your Supabase project is active

### "Email not sending"
- Verify SendGrid API key
- Check sender email is verified
- Review SendGrid activity logs

### Leads not appearing in dashboard
- Check database connection
- Verify leads table exists
- Check browser console for errors

## Next Steps

1. **Customize the qualification criteria** in `services/ai_qualifier.py`
2. **Adjust scoring thresholds** in `.env` (MIN_QUALIFICATION_SCORE)
3. **Customize email templates** in `services/notifications.py`
4. **Add more service types** in `templates/index.html`
5. **Set up automated follow-ups** (can be added to the system)

## Support

For issues or questions:
1. Check the error logs in your terminal
2. Review the code comments in each module
3. Verify all API keys are correct
4. Test each service individually
