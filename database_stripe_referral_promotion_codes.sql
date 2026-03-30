-- Stripe Promotion Code id per referrer (friend enters code at Checkout). Optional; created lazily by app.
-- Run in Supabase SQL Editor when deploying this feature.

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN IF NOT EXISTS stripe_referral_promotion_code_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN customers.stripe_referral_promotion_code_id IS 'Stripe Promotion Code id (prom_xxx) for this customer referral code; same underlying coupon as STRIPE_REFERRAL_COUPON_ID.';
