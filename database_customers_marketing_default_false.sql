-- Change marketing_opt_in default to false (GDPR: require explicit consent).
-- Existing rows keep their current value. New rows get false if not specified.
-- Run in Supabase SQL Editor.

ALTER TABLE customers ALTER COLUMN marketing_opt_in SET DEFAULT false;

COMMENT ON COLUMN customers.marketing_opt_in IS 'When false, customer has unsubscribed. Default false for new signups (GDPR).';
