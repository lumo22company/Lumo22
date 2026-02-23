# Insert test appointments for booking demo — 2 minutes

Run this in **Supabase SQL Editor** (bypasses RLS, no local setup needed):

1. Open https://supabase.com/dashboard → your project → **SQL Editor**
2. Paste and run:

```sql
-- Tomorrow: 10am–11am and 2pm–3pm already booked
-- Slots at 10:00 and 14:00 will be excluded (overlap)
INSERT INTO public.appointments (slot_start, slot_end)
VALUES 
  ((CURRENT_DATE + INTERVAL '1 day') + TIME '10:00', (CURRENT_DATE + INTERVAL '1 day') + TIME '11:00'),
  ((CURRENT_DATE + INTERVAL '1 day') + TIME '14:00', (CURRENT_DATE + INTERVAL '1 day') + TIME '15:00')
RETURNING id, slot_start, slot_end;
```

3. Test at **https://your-site.up.railway.app/book-demo**
   - Pick tomorrow's date in the calendar
   - You should see available times — 10:00 and 14:00 will be missing (already booked)
   - Click a slot to select it

**Different date?** Replace `CURRENT_DATE + INTERVAL '1 day'` with e.g. `'2026-02-25'::date`.
