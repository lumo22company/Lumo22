# Production environment setup

Set these variables in your **host’s dashboard** (e.g. Railway → your project → **Variables**). Never commit real secrets to git.

---

## Railway production checklist — do this

In Railway → your project → **Variables**, set or confirm:

| Variable      | Set to / check |
|---------------|-----------------|
| **FLASK_ENV** | `production` (not `development`) |
| **FLASK_DEBUG** | `False` (so debug mode and stack traces are off) |
| **SECRET_KEY** | A long random value (e.g. from `openssl rand -hex 32`), **not** `dev-secret-key-change-in-production` |
| **BASE_URL**  | Your live URL with no trailing slash, e.g. `https://www.lumo22.com` |

Save, then redeploy. Optional: you can remove **ACTIVATION_LINK** if you’re not using it (legacy).

---

## 1. Required in production (app will not start without these)

| Variable | Description | Example / how to get |
|----------|-------------|----------------------|
| **SECRET_KEY** | Flask session signing. Must not be the default. | Generate: `openssl rand -hex 32` (paste the output). |
| **SUPABASE_URL** | Supabase project URL | Supabase → Settings → API → Project URL |
| **SUPABASE_KEY** | Supabase anon key | Supabase → Settings → API → anon public |
| **STRIPE_SECRET_KEY** | Stripe API secret | Stripe Dashboard → Developers → API keys → Secret key (use `sk_live_` for live) |
| **STRIPE_WEBHOOK_SECRET** | Stripe webhook signing secret | Stripe Dashboard → Developers → Webhooks → your endpoint → Signing secret |
| **SENDGRID_API_KEY** | SendGrid API key | SendGrid → Settings → API Keys → Create |
| **BASE_URL** | Your site’s public URL (no trailing slash) | `https://www.lumo22.com` |

If any of these are missing or invalid when the app runs in production, startup will fail with a clear error and a pointer to this file.

---

## 2. Captions product (needed for checkout and pricing)

| Variable | Description |
|----------|-------------|
| **STRIPE_CAPTIONS_PRICE_ID** | One-off captions price (GBP) — `price_xxx` |
| **STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID** | Subscription price (GBP) — `price_xxx` |
| **STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID** | Extra platform one-off — `price_xxx` |
| **STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID** | Extra platform subscription — `price_xxx` |
| **STRIPE_CAPTIONS_STORIES_PRICE_ID** | Story Ideas one-off — `price_xxx` (optional) |
| **STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID** | Story Ideas subscription — `price_xxx` (optional) |

Optional for multi-currency: `STRIPE_CAPTIONS_PRICE_ID_USD`, `STRIPE_CAPTIONS_PRICE_ID_EUR`, and the matching subscription/extra/stories IDs.

---

## 3. Email and AI

| Variable | Description |
|----------|-------------|
| **FROM_EMAIL** | Sender address (must be verified in SendGrid) — e.g. `noreply@lumo22.com` |
| **FROM_NAME** | Sender name — e.g. `Lumo 22` |
| **AI_PROVIDER** | `anthropic` or `openai` |
| **ANTHROPIC_API_KEY** | Anthropic API key (if AI_PROVIDER=anthropic) |
| **OPENAI_API_KEY** | OpenAI API key (if AI_PROVIDER=openai) |

---

## 4. Optional but recommended

| Variable | Description |
|----------|-------------|
| **CRON_SECRET** | Secret for `/api/captions-send-reminders` (reminder emails). Generate: `openssl rand -hex 32` |
| **CAPTIONS_DELIVER_TEST_SECRET** | If set, `/api/captions-deliver-test` requires `?secret=...` (avoids accidental triggers) |
| **STRIPE_REFERRAL_COUPON_ID** | Stripe coupon ID for refer-a-friend (e.g. 10% off) |
| **FLASK_ENV** | Set to `production` on the host so the app treats the environment as production |

---

## 4b. OAuth — Google Sign-In (optional)

**Continue with Google** on `/login` and `/signup` appears only when both variables below are set. Run **`database_customers_oauth.sql`** in the Supabase SQL editor first (`password_hash` nullable + `google_sub`).

**Google Cloud Console** — register the callback URL (this is what fixes **Error 400: redirect_uri_mismatch**):

1. **Set `BASE_URL` on Railway** to your real public site, with **no** trailing slash (e.g. `https://www.lumo22.com`). Redeploy if you change it.
2. **Get the exact callback URL from your live app** (after deploy):
   - In a browser, open: `https://www.lumo22.com/oauth-config-check` (use your real domain).
   - Find the line under **“Copy this into Google”** — it looks like:  
     `https://www.lumo22.com/api/auth/oauth/google/callback`  
   - **Select that whole line** (triple-click or drag from `https` through `callback`) and **Copy** (Cmd+C / Ctrl+C).  
   - *Alternative:* open `https://www.lumo22.com/api/auth/oauth/status` in the browser; in the JSON, copy the value of **`redirect_uri`** (quotes not included — only the URL string).
3. **Paste it into Google Cloud Console:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/) → select your project.
   - **APIs & Services** → **Credentials**.
   - Under **OAuth 2.0 Client IDs**, click your **Web client** (the one whose Client ID matches `GOOGLE_OAUTH_CLIENT_ID` in Railway).
   - Under **Authorized redirect URIs**, click **+ ADD URI**.
   - **Paste** what you copied in step 2 into the new field. Do not add a trailing `/` or spaces.
   - Click **SAVE** at the bottom of the page. Google can take a minute or two to apply the change; try **Continue with Google** again after that.
4. **If you use a second domain** (e.g. a Railway URL for staging), repeat step 2 on that host’s `/oauth-config-check`, copy that different `redirect_uri`, and **ADD URI** again in the same Google client so **both** URLs are listed.

| Variable | Description |
|----------|-------------|
| **GOOGLE_OAUTH_CLIENT_ID** | Client ID ending in `.apps.googleusercontent.com` |
| **GOOGLE_OAUTH_CLIENT_SECRET** | Client secret |

---

## 5. Railway (or similar) steps

1. Open your project → **Variables** (or **Environment**).
2. Add each variable from **Section 1** (required). Use **Add variable** / **New variable**.
3. Add variables from **Section 2** and **Section 3** for captions and email/AI.
4. For **SECRET_KEY**: in a terminal run `openssl rand -hex 32`, then paste the result as the value.
5. For **CRON_SECRET** (if you use the reminder cron): run `openssl rand -hex 32` again and paste.
6. Set **BASE_URL** to your live URL, e.g. `https://www.lumo22.com` (no trailing slash).
7. Save. Redeploy so the new variables are picked up.

---

## 6. How to check it worked

- After deploy, open your site. If any **required** variable is missing or invalid, the app will not start and the logs will show:  
  `Production missing required configuration: SECRET_KEY, ... Set these in your host (e.g. Railway) Variables. See PRODUCTION_ENV_SETUP.md.`
- If the app starts, required config is present. Then run the manual test checklist (checkout, intake, account, emails) to confirm Stripe and SendGrid work end-to-end.
