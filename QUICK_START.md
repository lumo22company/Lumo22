# Quick Start Guide

Get your AI-powered lead system running in 5 minutes!

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Get Your API Keys

**Minimum required:**
- OpenAI API key: https://platform.openai.com/api-keys (add $5-10 credit)
- Supabase: https://supabase.com (free account)

**Optional (for full features):**
- Calendly: https://calendly.com (free tier)
- SendGrid: https://sendgrid.com (100 emails/day free)

## 3. Set Up Environment

```bash
cp .env.example .env
```

Edit `.env` and add:
- `OPENAI_API_KEY=sk-your-key-here`
- `SUPABASE_URL=https://your-project.supabase.co`
- `SUPABASE_KEY=your-supabase-key`

## 4. Create Database Table

1. Go to Supabase SQL Editor
2. Run the SQL from `init_db.py` or use this:

```sql
CREATE TABLE leads (
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
    qualification_details JSONB
);
```

## 5. Run the System

```bash
python app.py
```

## 6. Test It!

1. Open http://localhost:5000
2. Fill out the form
3. Check http://localhost:5000/dashboard to see your lead

## That's It! 🎉

Your system is now:
- ✅ Capturing leads automatically
- ✅ Qualifying leads with AI (0-100 score)
- ✅ Generating booking links for qualified leads
- ✅ Sending notifications
- ✅ Storing everything in your database

## Next Steps

- Customize the form in `templates/index.html`
- Adjust qualification criteria in `services/ai_qualifier.py`
- Set up webhooks for Typeform/Zapier (see `SETUP_GUIDE.md`)
- Deploy to Railway/Render for production

## Need Help?

See `SETUP_GUIDE.md` for detailed instructions and troubleshooting.
