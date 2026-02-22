-- Caption orders for 30 Days of Social Media Captions (automated flow)
-- Run this in Supabase SQL Editor after your main schema exists.

CREATE TABLE IF NOT EXISTS caption_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE,
    customer_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'awaiting_intake',
    stripe_session_id TEXT,
    intake JSONB,
    captions_md TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_caption_orders_token ON caption_orders(token);
CREATE INDEX IF NOT EXISTS idx_caption_orders_stripe_session_id ON caption_orders(stripe_session_id);
CREATE INDEX IF NOT EXISTS idx_caption_orders_status ON caption_orders(status);
CREATE INDEX IF NOT EXISTS idx_caption_orders_created_at ON caption_orders(created_at DESC);

COMMENT ON TABLE caption_orders IS '30 Days Captions: payment → intake → AI generation → delivery';
COMMENT ON COLUMN caption_orders.status IS 'awaiting_intake | intake_completed | generating | delivered | failed';
