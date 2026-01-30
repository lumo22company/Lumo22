-- Database Migration for SaaS System
-- This script updates the leads table and creates the businesses table
-- Run this in Supabase SQL Editor

-- Step 1: Add business_id column to leads table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'leads' AND column_name = 'business_id'
    ) THEN
        ALTER TABLE leads ADD COLUMN business_id TEXT;
        -- Set a default value for existing rows (you may want to handle this differently)
        UPDATE leads SET business_id = 'legacy' WHERE business_id IS NULL;
        -- Make it NOT NULL after setting defaults
        ALTER TABLE leads ALTER COLUMN business_id SET NOT NULL;
    END IF;
END $$;

-- Step 2: Create businesses table if it doesn't exist
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

-- Step 3: Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_leads_business_id ON leads(business_id);
CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses(email);
CREATE INDEX IF NOT EXISTS idx_businesses_api_key ON businesses(api_key);

-- Step 4: Verify tables exist
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name IN ('leads', 'businesses')
ORDER BY table_name, ordinal_position;
