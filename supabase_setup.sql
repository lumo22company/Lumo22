-- Supabase Database Setup SQL
-- Copy and paste this entire file into Supabase SQL Editor

-- Leads table (for businesses using the SaaS system)
CREATE TABLE IF NOT EXISTS leads (
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id TEXT NOT NULL,
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

-- Businesses table (for SaaS accounts)
CREATE TABLE IF NOT EXISTS businesses (
    business_id TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    service_types TEXT,
    status TEXT DEFAULT 'active',
    subscription_tier TEXT DEFAULT 'starter',
    api_key TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_leads_business_id ON leads(business_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_qualification_score ON leads(qualification_score);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses(email);
CREATE INDEX IF NOT EXISTS idx_businesses_api_key ON businesses(api_key);

-- Verify the table was created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name = 'leads';
