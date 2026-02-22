-- Digital Front Desk: on/off switch for auto-reply + domains to never reply to (e.g. internal).
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).

-- Add column: turn off auto-reply when customer wants to handle emails manually
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN auto_reply_enabled BOOLEAN DEFAULT true;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Add column: comma-separated domains we never auto-reply to (e.g. your own company = only reply to external/client emails)
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN skip_reply_domains TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

COMMENT ON COLUMN front_desk_setups.auto_reply_enabled IS 'When false, inbound emails to forwarding_email are not auto-replied (customer handles manually).';
COMMENT ON COLUMN front_desk_setups.skip_reply_domains IS 'Comma-separated domains (e.g. mybusiness.com) — we never auto-reply to senders whose email domain is in this list (keeps replies for clients only).';
