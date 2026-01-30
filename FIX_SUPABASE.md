# Fix Supabase Connection Issue

The Supabase connection test failed. Here's how to fix it:

## Option 1: Add RLS Policies (Recommended)

The new Supabase publishable keys require Row Level Security (RLS) policies.

### Steps:

1. **Go to Supabase SQL Editor** (left sidebar → SQL Editor)
2. **Click "New query"**
3. **Copy and paste this SQL:**

```sql
-- Enable Row Level Security
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Allow public inserts (for form submissions)
CREATE POLICY "Allow public inserts on leads"
ON leads
FOR INSERT
TO anon, authenticated
WITH CHECK (true);

-- Allow reading leads
CREATE POLICY "Allow public reads on leads"
ON leads
FOR SELECT
TO anon, authenticated
USING (true);

-- Allow updates
CREATE POLICY "Allow public updates on leads"
ON leads
FOR UPDATE
TO anon, authenticated
USING (true);
```

4. **Click "Run"**
5. **Test again** by running: `python3 test_system.py`

## Option 2: Use Legacy Keys (Alternative)

If you prefer to use legacy keys:

1. **Go to Project Settings → API Keys**
2. **Look for "Legacy keys" section** or a link that says "Legacy anon, service_role API keys"
3. **Copy the "anon" key** (not service_role)
4. **Share it with me** and I'll update your `.env` file

## Option 3: Check Table Exists

Make sure the `leads` table was created:

1. **Go to Table Editor** (left sidebar)
2. **Look for "leads" table**
3. **If it's not there**, run the SQL from `supabase_setup.sql` again

---

**Try Option 1 first** (adding RLS policies) - that's the most likely fix!
