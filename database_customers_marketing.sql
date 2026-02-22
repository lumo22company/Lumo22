-- Add marketing_opt_in to customers (for unsubscribe option)
-- Run in Supabase SQL Editor.

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN marketing_opt_in BOOLEAN DEFAULT true;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

COMMENT ON COLUMN customers.marketing_opt_in IS 'When false, customer has unsubscribed from marketing emails.';
