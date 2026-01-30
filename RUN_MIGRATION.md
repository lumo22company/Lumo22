# Database Migration Instructions

## Quick Steps

1. **Go to Supabase Dashboard**
   - Open https://supabase.com/dashboard
   - Select your project: `znnqzemtodqnxcnntdtb`

2. **Open SQL Editor**
   - Click "SQL Editor" in the left sidebar
   - Click "New query"

3. **Copy and Paste SQL**
   - Open the file `database_migration.sql` in this folder
   - Copy ALL the SQL code
   - Paste it into the Supabase SQL Editor

4. **Run the Migration**
   - Click "Run" button (or press Cmd/Ctrl + Enter)
   - Wait for it to complete

5. **Verify Success**
   - You should see a table showing the columns in `leads` and `businesses` tables
   - If you see any errors, they're likely just warnings about things that already exist (that's OK!)

## What This Does

- ✅ Adds `business_id` column to existing `leads` table
- ✅ Creates new `businesses` table for SaaS accounts
- ✅ Creates necessary indexes for performance
- ✅ Safe to run multiple times (won't break if already done)

## Next Steps After Migration

Once the migration is complete, you can:
1. Start the server: `python3 app.py`
2. Visit: http://localhost:5001
3. Sign up a test business account
4. Test the system!
