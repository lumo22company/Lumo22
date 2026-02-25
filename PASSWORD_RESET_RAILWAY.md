# Password reset not sending? Fix on Railway

If your email **is** in the `customers` table but you still don't receive the reset email, use the steps below to see what’s happening.

## 1. Check that the backend sees the right env

Open this URL in your browser (use your real domain):

**https://YOUR-RAILWAY-URL/api/auth/forgot-password/status**

You should see JSON like:

- `SUPABASE_SERVICE_ROLE_KEY_set: true` (needed so the app can read `customers` when RLS is on)
- `SENDGRID_API_KEY_set: true`
- `FROM_EMAIL` set to your sender address

If `SUPABASE_SERVICE_ROLE_KEY_set` is `false`, add `SUPABASE_SERVICE_ROLE_KEY` in Railway (Supabase → Settings → API → **service_role** key), then redeploy.

## 2. Try Forgot password and check Railway logs

1. Submit the forgot-password form with your email.
2. In Railway → your service → **Deployments** → latest deploy → **View logs** (or **Logs** tab).

You should see one of these:

- **`[Forgot password] Request for 'your@email.com' | SUPABASE_SERVICE_ROLE_KEY set=True ...`**  
  Request reached the backend.
- **`[Forgot password] No customer found for '...'`**  
  Backend did not find that email (wrong project, RLS, or key not set).
- **`[Forgot password] Customer found for '...', sending reset email`** then **`[SendGrid] Email sent OK`**  
  Email was sent; check spam and SendGrid Activity.
- **`[Forgot password] SendGrid failed`**  
  SendGrid env or config issue; check `FROM_EMAIL` and API key.

## 3. If service role was missing

1. Railway → **Variables** → add `SUPABASE_SERVICE_ROLE_KEY` = **service_role** from Supabase (Settings → API).
2. Redeploy (Variables save may auto-redeploy; if not, trigger a deploy).
3. Try forgot password again and recheck logs.

The app uses `SUPABASE_SERVICE_ROLE_KEY` when set so it can read and update `customers` for login and password reset when RLS is on.
