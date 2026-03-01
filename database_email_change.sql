-- Add columns for email change verification flow.
-- Run in Supabase SQL Editor: Dashboard → SQL Editor → New query → paste → Run.

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_change_token TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_change_new_email TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN email_change_expires TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
CREATE INDEX IF NOT EXISTS idx_customers_email_change_token ON customers(email_change_token) WHERE email_change_token IS NOT NULL;
