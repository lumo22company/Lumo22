# How to test the Smart Scheduling booking integration

## 1. Add a test appointment to Supabase

The slot picker shows existing appointments from the `appointments` table. Add one so you can see the "Group appointments together" filtering in action.

**Recommended: Supabase SQL Editor** (bypasses RLS)

1. Open your [Supabase Dashboard](https://supabase.com/dashboard) → your project → **SQL Editor**
2. Copy the contents of `scripts/insert_test_appointment.sql` (or the SQL below) and run it:

```sql
INSERT INTO public.appointments (slot_start, slot_end)
VALUES (
  (CURRENT_DATE + INTERVAL '1 day') + TIME '14:00',
  (CURRENT_DATE + INTERVAL '1 day') + TIME '15:00'
)
RETURNING id, slot_start, slot_end;
```

This inserts a 2pm–3pm appointment for tomorrow.

**Option B: Python script** (requires `SUPABASE_SERVICE_ROLE_KEY` in .env to bypass RLS)
```bash
python3 scripts/insert_test_appointment.py
# Or with a date: python3 scripts/insert_test_appointment.py 2026-02-15
```

**Option C: Insert manually in Supabase SQL Editor** (custom date)
```sql
-- Replace with your chosen date
INSERT INTO public.appointments (slot_start, slot_end)
VALUES (
  '2026-02-15 14:00:00+00'::timestamptz,   -- 2pm
  '2026-02-15 15:00:00+00'::timestamptz    -- 3pm
)
RETURNING *;
```

## 2. Open the booking demo page

- **Local:** http://localhost:5000/book-demo  
- **Live:** https://your-site.up.railway.app/book-demo  

## 3. Test the behaviour

1. **Pick a date** that matches your test appointment.
2. **Appointment duration:** Try 30, 60, or 90 minutes.
3. **Group appointments together:** Turn this OFF first – you should see all available times (e.g. 9:00–17:00 in 30 min slots).
4. **Group appointments together:** Turn it ON – you should see only slots near your existing appointment.
   - For a 2pm–3pm booking and 60 min buffer: expect 1pm, 3pm, and nearby times; 2pm should not appear (it overlaps).
   - For a 90 min appointment: 11:30am should be the earliest slot before a 2pm appointment (2.5 hrs earlier).
5. **Buffer:** Change "Show slots within how many minutes" to 30 – fewer slots should appear.

## 4. Test via API (optional)

```bash
# All slots for a day (no grouping)
curl "https://your-site.up.railway.app/api/available-slots?date=2026-02-15&slot_minutes=60"

# Grouped slots, 60 min buffer
curl "https://your-site.up.railway.app/api/available-slots?date=2026-02-15&slot_minutes=60&tight_schedule=true&gap_minutes=60"
```

## Requirements

- `appointments` table exists in Supabase (run `database_appointments.sql` if needed)
- `SUPABASE_URL` and `SUPABASE_KEY` in `.env` / Railway variables
