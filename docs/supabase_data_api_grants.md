# Supabase Data API Grants

Supabase is changing the default table exposure behaviour for the `public` schema:

- New projects: from May 30, 2026
- Existing projects: new tables from October 30, 2026

After enforcement, a table can have valid RLS policies and still be invisible to
PostgREST, GraphQL, and `supabase-js` unless explicit grants are present.

## New Table Template

Use this pattern whenever creating a new `public` table.

```sql
CREATE TABLE IF NOT EXISTS my_new_table (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Required for the Supabase Data API to expose the table.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE my_new_table TO anon, authenticated;
GRANT ALL ON TABLE my_new_table TO service_role;

ALTER TABLE my_new_table ENABLE ROW LEVEL SECURITY;

-- Add narrow policies after enabling RLS.
-- CREATE POLICY "..." ON my_new_table ...
```

## When to Use Narrower Grants

Only grant the operations the browser/client actually needs:

```sql
GRANT SELECT ON TABLE public_read_only_table TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE user_owned_table TO authenticated;
GRANT ALL ON TABLE internal_backend_table TO service_role;
```

Keep sensitive backend-only tables hidden from `anon` and `authenticated` unless
there is a deliberate client-side use case and matching RLS policy.

## Existing Tables

Existing tables in the current Supabase project keep their current behaviour.
Do not retrofit grants blindly. Use Supabase Dashboard -> Advisors -> Security
Advisor before changing exposure on existing tables.

## Mental Model

- `GRANT` controls whether the table is visible/usable through the Data API.
- RLS controls which rows each role can read or mutate.
- Backend service-role code still needs table privileges, even though it bypasses RLS.
