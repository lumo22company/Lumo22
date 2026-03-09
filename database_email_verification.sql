-- Add columns for email verification on signup.
-- Run in Supabase SQL Editor: Dashboard → SQL Editor → New query → paste → Run.
-- Existing customers default to email_verified=true so they are not locked out.

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_verified BOOLEAN DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_verification_token TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_verification_expires TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Existing customers: mark as verified (they signed up before this flow)
UPDATE customers SET email_verified = true WHERE email_verified IS NULL;

-- Default new signups to unverified
ALTER TABLE customers ALTER COLUMN email_verified SET DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_customers_email_verification_token ON customers(email_verification_token) WHERE email_verification_token IS NOT NULL;
