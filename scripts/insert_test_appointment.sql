-- Insert a test appointment for the booking demo (2pm-3pm, 60 min)
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard → your project → SQL Editor
-- Replace the date below with your desired test date (or use tomorrow)

INSERT INTO public.appointments (slot_start, slot_end)
VALUES (
  (CURRENT_DATE + INTERVAL '1 day') + TIME '14:00',
  (CURRENT_DATE + INTERVAL '1 day') + TIME '15:00'
)
RETURNING id, slot_start, slot_end;

-- Then go to /book-demo, pick that date, and turn on "Group appointments together"
