# Supabase RLS quick check (5 minutes)

Use this when you want to verify row-level security without changing anything.

## 1) Run the audit query

1. Open Supabase project → **SQL Editor**.
2. Open file `database_security_rls_audit.sql` from this repo.
3. Copy/paste into SQL Editor and click **Run**.

The script is read-only. It prints 4 result tables.

## 2) How to read results

- **RLS enabled check**
  - All sensitive tables should show `PASS` and `rls_enabled=true`.
- **Policy inventory**
  - Snapshot of current policies.
- **Broad SELECT policy**
  - If you see `WARN: broad row visibility` on `caption_orders`/`customers`, anon/authenticated could read too much if those keys are exposed.
- **Next action**
  - Gives a plain-English recommendation from current state.

## 3) If you get warnings

- If your backend can use `SUPABASE_SERVICE_ROLE_KEY`, prefer tighter/deny anon/auth policies on sensitive tables.
- Existing helper scripts in repo:
  - `database_customers_rls.sql`
  - `database_rls_policies_anon_authenticated_deny.sql`
  - `database_rls_fix.sql`
  - `database_rls_fix_warnings.sql`

## 4) Safety notes

- Never put `SUPABASE_SERVICE_ROLE_KEY` in frontend code.
- Re-run this audit after major auth/data-model changes.
