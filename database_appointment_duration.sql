-- Add appointment_duration_minutes to front_desk_setups.
-- Set by the business during setup (from their Calendly/Fresha config).
-- Used when filtering slots so we show the correct availability.
-- Run in Supabase SQL Editor.

ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS appointment_duration_minutes INTEGER NOT NULL DEFAULT 60;

COMMENT ON COLUMN front_desk_setups.appointment_duration_minutes IS 'Duration of appointments in minutes (from their booking system). Used for slot filtering and overlap checks.';
