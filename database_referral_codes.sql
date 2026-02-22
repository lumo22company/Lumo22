-- Refer-a-friend: unique codes per customer, track who referred whom.
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> paste -> Run).

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN IF NOT EXISTS referral_code TEXT UNIQUE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN IF NOT EXISTS referred_by_customer_id UUID REFERENCES customers(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_customers_referral_code ON customers(referral_code) WHERE referral_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_referred_by ON customers(referred_by_customer_id) WHERE referred_by_customer_id IS NOT NULL;

COMMENT ON COLUMN customers.referral_code IS 'Unique code for refer-a-friend (e.g. share signup?ref=CODE)';
COMMENT ON COLUMN customers.referred_by_customer_id IS 'Customer who referred this user (if signed up with ref code)';
