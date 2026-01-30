# API Keys Setup Guide

Follow these steps to get your API keys and configure the system.

## 🔑 Required API Keys (Minimum)

### 1. OpenAI API Key (Required for AI Qualification)

**Cost:** ~$0.01-0.05 per lead qualification

**Steps:**
1. Go to https://platform.openai.com
2. Sign up or log in
3. Go to **API Keys** section (https://platform.openai.com/api-keys)
4. Click **"Create new secret key"**
5. Copy the key (starts with `sk-`)
6. **Add credits:** Go to Billing → Add credits ($5-10 is enough to start)
7. Add to `.env`:
   ```
   OPENAI_API_KEY=sk-your-actual-key-here
   ```

**Why:** Powers the AI qualification engine that scores leads 0-100.

---

### 2. Supabase (Required for Database)

**Cost:** FREE (500MB storage, perfect for MVP)

**Steps:**
1. Go to https://supabase.com
2. Click **"Start your project"** → Sign up (free)
3. Create a new project:
   - Choose a name (e.g., "lumo22-leads")
   - Set a database password (save this!)
   - Choose a region close to you
   - Wait 2-3 minutes for setup

4. **Get your credentials:**
   - Go to **Project Settings** → **API**
   - Copy **"Project URL"** (looks like: `https://xxxxx.supabase.co`)
   - Copy **"anon public"** key (long string)

5. **Create the database table:**
   - Go to **SQL Editor** in Supabase dashboard
   - Click **"New query"**
   - Paste this SQL:

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

   - Click **"Run"**

6. Add to `.env`:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your-anon-key-here
   ```

**Why:** Stores all your leads securely in a PostgreSQL database.

---

## 🎯 Optional API Keys (Recommended)

### 3. Calendly (For Automated Booking)

**Cost:** FREE (1 event type) or $10/month (unlimited)

**Steps:**
1. Go to https://calendly.com
2. Sign up for free
3. Create an event type:
   - Click **"Event Types"** → **"New Event Type"**
   - Choose **"One-on-One"** or **"Group"**
   - Set duration (e.g., 30 minutes)
   - Save and note the URL (e.g., `your-username/consultation`)

4. **Get API access:**
   - Go to **Integrations** → **API & Webhooks**
   - Click **"Personal Access Token"**
   - Create token with read/write permissions
   - Copy the token

5. Add to `.env`:
   ```
   CALENDLY_API_KEY=your-token-here
   CALENDLY_EVENT_TYPE_ID=your-username/consultation
   ```

**Why:** Automatically generates booking links for qualified leads.

**Note:** If not configured, the system will use email fallback.

---

### 4. SendGrid (For Email Notifications)

**Cost:** FREE (100 emails/day) or $15/month (50k emails)

**Steps:**
1. Go to https://sendgrid.com
2. Sign up (free tier available)
3. **Verify your sender:**
   - Go to **Settings** → **Sender Authentication**
   - Click **"Verify a Single Sender"**
   - Enter your email and verify it

4. **Get API key:**
   - Go to **Settings** → **API Keys**
   - Click **"Create API Key"**
   - Name it (e.g., "Lead System")
   - Choose **"Full Access"** or **"Mail Send"** permissions
   - Copy the key (starts with `SG.`)

5. Add to `.env`:
   ```
   SENDGRID_API_KEY=SG.your-key-here
   FROM_EMAIL=your-verified-email@yourdomain.com
   ```

**Why:** Sends automated emails to leads and notifications to you.

**Note:** If not configured, emails won't be sent (system will still work).

---

### 5. Twilio (For SMS Notifications - Optional)

**Cost:** ~$0.0075 per SMS (pay-per-use)

**Steps:**
1. Go to https://www.twilio.com
2. Sign up (free trial with $15 credit)
3. **Get a phone number:**
   - Go to **Phone Numbers** → **Get a number**
   - Choose a number (free trial number available)

4. **Get credentials:**
   - Go to **Account** → **API Keys & Tokens**
   - Copy **Account SID**
   - Copy **Auth Token**

5. Add to `.env`:
   ```
   TWILIO_ACCOUNT_SID=your-account-sid
   TWILIO_AUTH_TOKEN=your-auth-token
   TWILIO_PHONE_NUMBER=+1234567890
   ```

**Why:** Sends SMS notifications (optional feature).

**Note:** Completely optional. System works fine without it.

---

## ✅ After Adding Keys

1. **Edit `.env` file** with your actual keys
2. **Run setup check:**
   ```bash
   python3 check_setup.py
   ```
3. **If all green, start the system:**
   ```bash
   ./run.sh
   # or
   python3 app.py
   ```

## 💰 Cost Summary

| Service | Free Tier | Monthly Cost (if needed) |
|---------|-----------|-------------------------|
| OpenAI | Pay-per-use | ~$0.01-0.05/lead |
| Supabase | 500MB free | $0 (free tier sufficient) |
| Calendly | 1 event type | $0 or $10/month |
| SendGrid | 100 emails/day | $0 or $15/month |
| Twilio | Trial credits | ~$0.0075/SMS |

**Total for MVP: $0-10/month** (depending on volume)

---

## 🆘 Troubleshooting

### "Invalid API key" errors
- Double-check you copied the full key (no spaces)
- Make sure you're using the right key type (e.g., OpenAI API key, not organization key)
- Check if the key has expired or been revoked

### "Database connection failed"
- Verify Supabase project is active (not paused)
- Check SUPABASE_URL format (should be `https://xxxxx.supabase.co`)
- Ensure the leads table was created successfully

### "Email not sending"
- Verify sender email in SendGrid
- Check SendGrid activity logs
- Ensure FROM_EMAIL matches verified sender

---

## 🔒 Security Notes

- **Never commit `.env` to git** (already in `.gitignore`)
- **Don't share your API keys** publicly
- **Rotate keys** if accidentally exposed
- **Use environment variables** in production (not hardcoded)

---

Need help? Check `SETUP_GUIDE.md` for detailed instructions.
