-- Digital Front Desk: optional tight scheduling (show slots only near existing same-day bookings).
-- Run in Supabase SQL Editor. Safe to run multiple times.

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS tight_scheduling_enabled BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE front_desk_setups ADD COLUMN IF NOT EXISTS minimum_gap_between_appointments INTEGER NOT NULL DEFAULT 60;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

COMMENT ON COLUMN front_desk_setups.tight_scheduling_enabled IS 'If true, only show slots within minimum_gap_between_appointments of existing same-day bookings; if no bookings that day, show all slots';
COMMENT ON COLUMN front_desk_setups.minimum_gap_between_appointments IS 'Minutes: window around existing bookings for tight scheduling (default 60). Only applies when tight_scheduling_enabled is true';
