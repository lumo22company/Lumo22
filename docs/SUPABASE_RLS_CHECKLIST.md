# Supabase RLS quick check (5 minutes)

Use this when you want to verify row-level security without changing anything.

## 1) Run the audit query

1. Open Supabase project → **SQL Editor**.
2. Open file `database_security_rls_audit.sql` from this repo.
3. Copy/paste into SQL Editor and click **Run**.

The script is read-only. It returns **one combined results table** with four sections (rows are grouped by the `section` column).

## 2) How to read results

Columns: `section`, `item`, `result`, `detail`.

- **RLS enabled check**
  - Each `item` is a table name. `result` should be `PASS` for every expected table. `detail` shows `true`/`false` for whether RLS is enabled on that table.
- **Policy inventory**
  - One row per policy. `result` is the policy command (`SELECT`, `INSERT`, etc.). `detail` includes roles and the `USING` / `WITH CHECK` expressions.
- **Broad SELECT policy**
  - Only `SELECT` policies on `caption_orders`, `customers`, and `deleted_account_emails`. If `result` is `WARN: broad row visibility`, anon/authenticated could read too much if those keys are exposed.
- **Next action**
  - One summary row with a plain-English recommendation from current state.

## 3) If you get warnings

- If your backend can use `SUPABASE_SERVICE_ROLE_KEY`, prefer tighter/deny anon/auth policies on sensitive tables.
- For the specific warning **\"tighten caption_orders SELECT for anon/authenticated\"**, run:
  - `database_caption_orders_rls_harden_service_role.sql`
  - then re-run `database_security_rls_audit.sql` (the warning should clear)
- For the specific warning **\"tighten deleted_account_emails SELECT for anon/authenticated\"**, run:
  - `database_deleted_account_emails_rls_harden_service_role.sql`
  - then re-run `database_security_rls_audit.sql` (the warning should clear)
- Existing helper scripts in repo:
  - `database_customers_rls.sql`
  - `database_rls_policies_anon_authenticated_deny.sql`
  - `database_rls_fix.sql`
  - `database_rls_fix_warnings.sql`

## 4) Safety notes

- Never put `SUPABASE_SERVICE_ROLE_KEY` in frontend code.
- Re-run this audit after major auth/data-model changes.
