-- Digital Front Desk: optional reply style examples for matching customer's voice.
-- Run in Supabase SQL Editor. Tone column already exists from database_front_desk_preferences.sql.

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS reply_style_examples TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

COMMENT ON COLUMN front_desk_setups.reply_style_examples IS 'Optional: 1-2 example email replies from the business; AI matches this style in auto-replies';
