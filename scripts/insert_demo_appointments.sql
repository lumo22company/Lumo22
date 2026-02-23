-- Insert demo appointments for /book-demo testing
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Tomorrow: 10–11am and 2–3pm booked; 10:00 and 14:00 slots will be excluded

DELETE FROM public.appointments
WHERE slot_start >= (CURRENT_DATE + INTERVAL '1 day')::date
  AND slot_start < (CURRENT_DATE + INTERVAL '2 days')::date;

INSERT INTO public.appointments (slot_start, slot_end)
VALUES 
  (((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '10:00') AT TIME ZONE 'UTC', ((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '11:00') AT TIME ZONE 'UTC'),
  (((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '14:00') AT TIME ZONE 'UTC', ((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '15:00') AT TIME ZONE 'UTC')
RETURNING id, slot_start, slot_end;
