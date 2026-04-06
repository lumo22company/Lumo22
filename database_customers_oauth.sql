-- OAuth (Google): nullable password for Google-only accounts; stable Google subject id.
-- Run in Supabase SQL Editor after `customers` exists.

ALTER TABLE customers ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE customers ADD COLUMN IF NOT EXISTS google_sub TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_google_sub ON customers(google_sub) WHERE google_sub IS NOT NULL;

COMMENT ON COLUMN customers.google_sub IS 'Google OIDC subject (sub); unique when set.';
