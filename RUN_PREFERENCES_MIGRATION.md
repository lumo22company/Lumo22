# Run Front Desk Preferences Migration (1 min)

Adds enquiry_types, opening_hours, reply_same_day, reply_24h, tone, good_lead_rules to `front_desk_setups`.

## Option A: Supabase SQL Editor (no DATABASE_URL needed)

1. **Open SQL Editor:**  
   [Supabase SQL Editor → New query](https://supabase.com/dashboard/project/znnqzemtodqnxcnntdtb/sql/new)  
   (Log in if prompted)

2. **Copy the SQL:** Open `database_front_desk_preferences.sql` in your editor, select all (Cmd+A), copy (Cmd+C).

3. **Paste and run:** Paste into the SQL Editor, click **Run** (or Cmd+Enter).

4. **Done.** You should see success — the chat setup step 2 fields are now persisted and used in reply generation.

---

## Option B: Migration script (requires DATABASE_URL)

1. In `.env`, set `DATABASE_URL` with your real Supabase postgres password  
   (Supabase → Project Settings → Database → Connection string → URI)

2. Run:
   ```bash
   python3 run_front_desk_preferences_migration.py
   ```
