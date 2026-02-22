-- Appointments (existing bookings) for available-slots API.
-- Used to filter slots when "Group appointments together" is on.
-- Run in Supabase SQL Editor. Safe to run multiple times.

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_start TIMESTAMPTZ NOT NULL,
    slot_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_appointments_slot_start ON appointments(slot_start);

-- RLS: allow app (service role) to read and insert
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS appointments_select ON appointments;
CREATE POLICY appointments_select ON appointments FOR SELECT USING (true);
DROP POLICY IF EXISTS appointments_insert ON appointments;
CREATE POLICY appointments_insert ON appointments FOR INSERT WITH CHECK (true);

COMMENT ON TABLE appointments IS 'Existing bookings for a day; used by GET /api/available-slots when tight scheduling is on';

-- -----------------------------------------------------------------------------
-- Example test queries (run in Supabase SQL Editor to seed or verify).
-- The app uses the service role key, so it bypasses RLS; these are for manual use.
-- -----------------------------------------------------------------------------
-- Insert one appointment (e.g. tomorrow at 12:00) so /book "Group appointments" shows filtered slots:
--   INSERT INTO public.appointments (slot_start, slot_end)
--   VALUES (
--     date_trunc('day', now() + interval '1 day') + time '12:00',
--     date_trunc('day', now() + interval '1 day') + time '12:30'
--   )
--   RETURNING *;
-- Insert with explicit date:
--   INSERT INTO public.appointments (slot_start, slot_end)
--   VALUES ('2026-03-01 09:00:00+00'::timestamptz, '2026-03-01 09:30:00+00'::timestamptz)
--   RETURNING *;
-- Select all: SELECT id, slot_start, slot_end, created_at FROM public.appointments ORDER BY slot_start LIMIT 50;
