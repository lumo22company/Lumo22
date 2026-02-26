-- Referrer reward: one 10% off per referral, applied to the referrer's next billing period(s).
-- No stacking: 2 referrals = 10% off next 2 invoices, not 20% off one.
-- Run in Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> paste -> Run).
-- After deploying: Stripe Dashboard -> Webhooks -> your endpoint -> Add event: invoice.created

-- Credits bank: how many "10% off next invoice" the referrer has earned (one per referred friend who paid).
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN IF NOT EXISTS referral_discount_credits INTEGER NOT NULL DEFAULT 0;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN customers.referral_discount_credits IS 'Number of 10% off credits for referrer reward (one per referred friend who completed captions payment). Applied to next billing period(s), one per invoice.';

-- Track which invoices we already applied a referrer discount to (idempotent webhook).
CREATE TABLE IF NOT EXISTS referral_discount_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    stripe_invoice_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_referral_redemptions_customer ON referral_discount_redemptions(customer_id);
CREATE INDEX IF NOT EXISTS idx_referral_redemptions_invoice ON referral_discount_redemptions(stripe_invoice_id);
COMMENT ON TABLE referral_discount_redemptions IS 'One row per invoice we applied a referrer 10% discount to; prevents double-apply on webhook retries.';
