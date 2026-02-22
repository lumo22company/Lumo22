-- Digital Front Desk setups: form submissions after payment (for connecting enquiry email + booking)
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).
-- After this table exists, the setup form saves here and you get a one-click "Mark as connected" link.

CREATE TABLE IF NOT EXISTS front_desk_setups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    done_token TEXT NOT NULL UNIQUE,
    customer_email TEXT NOT NULL,
    business_name TEXT NOT NULL,
    enquiry_email TEXT NOT NULL,
    booking_link TEXT,
    forwarding_email TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add column if table already existed without it (run once)
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN forwarding_email TEXT UNIQUE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_front_desk_setups_done_token ON front_desk_setups(done_token);
CREATE INDEX IF NOT EXISTS idx_front_desk_setups_enquiry_email ON front_desk_setups(enquiry_email);
CREATE INDEX IF NOT EXISTS idx_front_desk_setups_forwarding_email ON front_desk_setups(forwarding_email);
CREATE INDEX IF NOT EXISTS idx_front_desk_setups_status ON front_desk_setups(status);
CREATE INDEX IF NOT EXISTS idx_front_desk_setups_created_at ON front_desk_setups(created_at DESC);

COMMENT ON TABLE front_desk_setups IS 'Digital Front Desk: setup form after payment; status = pending | connected';
COMMENT ON COLUMN front_desk_setups.done_token IS 'Secret token for one-click Mark as connected link';
COMMENT ON COLUMN front_desk_setups.forwarding_email IS 'Unique address for inbound (e.g. reply-abc@inbound.lumo22.com); enquirers email this, we auto-reply';
