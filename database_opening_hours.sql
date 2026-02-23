-- Add work_start and work_end to front_desk_setups (HH:MM from business's Calendly/Fresha).
-- Run in Supabase SQL Editor.

ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS work_start TEXT DEFAULT '09:00';
ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS work_end TEXT DEFAULT '17:00';

COMMENT ON COLUMN front_desk_setups.work_start IS 'Start of working day, HH:MM (from their booking platform). Used for slot availability.';
COMMENT ON COLUMN front_desk_setups.work_end IS 'End of working day, HH:MM (from their booking platform). Used for slot availability.';
