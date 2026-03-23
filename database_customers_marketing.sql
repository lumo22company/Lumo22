-- Add marketing_opt_in to customers (for marketing toggle + GDPR)
-- Run in Supabase SQL Editor.
-- If the column already exists with DEFAULT true, also run database_customers_marketing_default_false.sql

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN marketing_opt_in BOOLEAN DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

COMMENT ON COLUMN customers.marketing_opt_in IS 'Marketing emails: true only after explicit opt-in. Default false (GDPR).';
