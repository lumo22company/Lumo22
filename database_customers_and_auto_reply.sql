-- Run this once in Supabase SQL Editor: Dashboard → SQL Editor → New query → paste → Run.
-- Creates customers table + adds auto_reply columns to front_desk_setups.

-- 1. Customers table (for account dashboard)
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
COMMENT ON TABLE customers IS 'Lumo 22 customer accounts: DFD, Chat, Captions. One per email.';

-- 2. Auto-reply columns (for DFD pause/resume)
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN auto_reply_enabled BOOLEAN DEFAULT true;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN skip_reply_domains TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN front_desk_setups.auto_reply_enabled IS 'When false, inbound emails are not auto-replied.';
COMMENT ON COLUMN front_desk_setups.skip_reply_domains IS 'Comma-separated domains we never auto-reply to.';

-- 3. Stripe IDs for caption subscriptions (billing portal)
DO $$ BEGIN
    ALTER TABLE caption_orders ADD COLUMN stripe_customer_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE caption_orders ADD COLUMN stripe_subscription_id TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- 4. Marketing opt-in (for unsubscribe in account dashboard)
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN marketing_opt_in BOOLEAN DEFAULT true;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
COMMENT ON COLUMN customers.marketing_opt_in IS 'When false, customer has unsubscribed from marketing emails.';

-- 5. Password reset (for forgot password flow)
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN password_reset_token TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN password_reset_expires TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token) WHERE password_reset_token IS NOT NULL;
