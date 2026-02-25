# Password reset not sending? Fix on Railway

If your email **is** in the `customers` table but you still don't receive the reset email, the app is likely using the **anon** key. When RLS is enabled on `customers`, the anon key cannot read any rows — so "customer not found" and no email is sent.

## Fix

1. **Add the service role key in Railway**
   - Railway → your project → **Variables**
   - Add: `SUPABASE_SERVICE_ROLE_KEY` = your **service_role** secret from Supabase  
   - In Supabase: **Settings → API** → copy the **service_role** key (not the anon key).

2. **Redeploy** (e.g. trigger a new deploy or push a commit).

3. Try **Forgot password** again.

The app now uses `SUPABASE_SERVICE_ROLE_KEY` when set (and falls back to `SUPABASE_KEY`), so the backend can read and update `customers` for login and password reset even when RLS is on.
