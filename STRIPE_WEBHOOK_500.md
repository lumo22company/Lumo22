# Stripe webhook returns 500 Internal Server Error

When Stripe shows **500 ERR** for your webhook, the request reaches your app but something crashes inside the handler. The **exact error** is in your Railway logs.

---

## 1. Get the real error from Railway logs

1. Open **Railway** → your Lumo 22 service → **Deployments** → latest deployment.
2. Click **View logs** (or **Deploy logs**).
3. Find the time of the failed webhook (e.g. 2 Feb 2026, 11:48).
4. Look for lines like:
   - `[Stripe webhook] captions handler error: ...`
   - `[Stripe webhook] unexpected error: ...`
   - A **traceback** (multiple lines starting with `Traceback`, `File "...", line X`, and the exception type/message).

The **last line** of the traceback (e.g. `ValueError: Supabase configuration missing` or `RuntimeError: Failed to create caption order`) is the cause.

---

## 2. Common causes and fixes

| Log error | Cause | Fix |
|----------|--------|-----|
| **Supabase configuration missing** | `SUPABASE_URL` or `SUPABASE_KEY` missing on Railway | In Railway → Variables, set **SUPABASE_URL** and **SUPABASE_KEY** (from Supabase project Settings → API). Redeploy. |
| **Failed to create caption order** / **permission denied** / **new row violates row-level security** | Table missing or RLS blocking insert | 1) In Supabase SQL Editor, run [database_caption_orders.sql](database_caption_orders.sql) to create the table. 2) Then run [database_caption_orders_rls.sql](database_caption_orders_rls.sql) to allow inserts. |
| **relation "caption_orders" does not exist** | Table not created in Supabase | In Supabase SQL Editor, run [database_caption_orders.sql](database_caption_orders.sql). |
| **Email NOT sent (no API key)** | SendGrid not configured on Railway | In Railway → Variables, set **SENDGRID_API_KEY** and **FROM_EMAIL**. Redeploy. (Email won’t send but webhook can still return 200 if you fix this and Supabase.) |
| **SendGrid ... 403** / **401** | Invalid SendGrid API key or from address | Check **SENDGRID_API_KEY** and **FROM_EMAIL** in Railway; in SendGrid verify the sender (FROM_EMAIL). |
| **Invalid non-printable ASCII character in URL** | **BASE_URL** in Railway has a hidden character (e.g. newline, carriage return) | In Railway → Variables, edit **BASE_URL**. Delete the value and type it again (e.g. `https://lumo-22-production.up.railway.app`) with no spaces or line breaks. Save and redeploy. The app now sanitizes BASE_URL; redeploy so the fix is active. |

---

## 3. After you fix it

1. Save the variable or run the SQL in Supabase.
2. If you changed Railway variables, wait for redeploy (1–2 minutes).
3. In Stripe, open the failed event and click **Resend** (or do a new test payment).
4. Check Railway logs again: you should see `[Stripe webhook] Order created` and `[SendGrid] Email sent OK` and no 500.

---

## 4. If the policy already exists (Supabase)

If you run `database_caption_orders_rls.sql` and get **policy already exists**, that’s fine — it means RLS is already set up. Drop the duplicate policy name if you need to re-run, or skip that policy:

```sql
-- Only if you need to recreate:
DROP POLICY IF EXISTS "Allow caption_orders insert" ON caption_orders;
DROP POLICY IF EXISTS "Allow caption_orders select" ON caption_orders;
DROP POLICY IF EXISTS "Allow caption_orders update" ON caption_orders;
```

Then run the `CREATE POLICY` lines again.

---

**Summary:** 500 = something crashed. Check Railway logs for the traceback, then fix the cause (usually Supabase vars/table/RLS or SendGrid vars).
