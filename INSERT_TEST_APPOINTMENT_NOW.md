# Insert test appointments for booking demo — 2 minutes

**Required:** Add `SUPABASE_SERVICE_ROLE_KEY` to Railway variables (Supabase → Settings → API → service_role). The appointments table uses RLS; the service role lets the app read existing bookings to exclude those slots.

Run this in **Supabase SQL Editor** (bypasses RLS, no local setup needed):

1. Open https://supabase.com/dashboard → your project → **SQL Editor**
2. (Optional) Clear old test data: `DELETE FROM public.appointments;`
3. Paste and run:

```sql
-- Tomorrow (UTC): 10am–11am and 2pm–3pm already booked
-- Slots at 10:00 and 14:00 will be excluded (overlap)
-- Uses AT TIME ZONE 'UTC' for reliable storage regardless of session
INSERT INTO public.appointments (slot_start, slot_end)
VALUES 
  (((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '10:00') AT TIME ZONE 'UTC', ((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '11:00') AT TIME ZONE 'UTC'),
  (((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '14:00') AT TIME ZONE 'UTC', ((CURRENT_DATE + INTERVAL '1 day')::timestamp + TIME '15:00') AT TIME ZONE 'UTC')
RETURNING id, slot_start, slot_end;
```

3. Test at **https://your-site.up.railway.app/book-demo**
   - Pick tomorrow's date in the calendar
   - You should see available times — 10:00 and 14:00 will be missing (already booked)
   - Click a slot to select it

**Different date?** Replace `CURRENT_DATE + INTERVAL '1 day'` with e.g. `'2026-02-25'::date`.
