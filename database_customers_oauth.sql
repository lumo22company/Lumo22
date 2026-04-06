-- OAuth (Google / Apple): nullable password for IdP-only accounts; stable provider subject ids.
-- Run in Supabase SQL Editor after `customers` exists.

ALTER TABLE customers ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE customers ADD COLUMN IF NOT EXISTS google_sub TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS apple_sub TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_google_sub ON customers(google_sub) WHERE google_sub IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_apple_sub ON customers(apple_sub) WHERE apple_sub IS NOT NULL;

COMMENT ON COLUMN customers.google_sub IS 'Google OIDC subject (sub); unique when set.';
COMMENT ON COLUMN customers.apple_sub IS 'Apple Sign In subject (sub); unique when set.';
