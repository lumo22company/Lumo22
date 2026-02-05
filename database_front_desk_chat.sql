-- Digital Front Desk: add columns for Website Chat (widget) and chat-only product.
-- Run in Supabase SQL Editor. Safe to run multiple times (uses DO blocks).

-- Product type: 'front_desk' (default) or 'chat_only'
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS product_type TEXT NOT NULL DEFAULT 'front_desk';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Chat widget: enabled flag and unique key for embed (used by /api/chat)
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS chat_enabled BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS chat_widget_key TEXT UNIQUE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Optional context for chat replies (business description, tone, etc.)
DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS business_description TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_front_desk_setups_chat_widget_key ON front_desk_setups(chat_widget_key) WHERE chat_widget_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_front_desk_setups_product_type ON front_desk_setups(product_type);

COMMENT ON COLUMN front_desk_setups.product_type IS 'front_desk = full setup with email; chat_only = Website Chat Widget product only';
COMMENT ON COLUMN front_desk_setups.chat_widget_key IS 'Unique key for embed script and /api/chat; set when chat is enabled';
COMMENT ON COLUMN front_desk_setups.business_description IS 'Optional text for chat context (services, tone, FAQs)';
