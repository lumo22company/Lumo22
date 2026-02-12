# Run migrations (1 minute, no DATABASE_URL needed)

Run migrations directly in Supabase — no connection string required.

## Steps

1. **Open your project's SQL Editor:**  
   [https://supabase.com/dashboard/project/znnqzemtodqnxcnntdtb/sql/new](https://supabase.com/dashboard/project/znnqzemtodqnxcnntdtb/sql/new)  
   (Log in to Supabase if prompted)

2. **Copy the SQL:** Open the file `database_customers_and_auto_reply.sql` in Cursor, select all (Cmd+A), and copy (Cmd+C).

3. **Paste and run:** Paste into the SQL Editor box and click **Run** (or press Cmd+Enter).

4. **Done.** You should see "Success" — the account dashboard and auto-reply are ready.

The migration adds: **stripe_customer_id** and **stripe_subscription_id** (billing portal), **password_reset_token** and **password_reset_expires** (forgot password). Safe to re-run.

**Alternative:** If you have `DATABASE_URL` in `.env`, run `python3 run_customers_and_auto_reply_migration.py` instead.
