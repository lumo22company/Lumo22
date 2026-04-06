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

## 4b. OAuth — Google and Sign in with Apple (optional)

Buttons on `/login` and `/signup` appear only when the matching variables are set. Run **`database_customers_oauth.sql`** in the Supabase SQL editor first (`password_hash` nullable + `google_sub` / `apple_sub`).

**Google Cloud Console** (APIs & Services → Credentials → OAuth 2.0 Client ID, type *Web application*):

- **Authorized redirect URI:** `https://www.lumo22.com/api/auth/oauth/google/callback` (add your Railway preview URL for staging if needed)

| Variable | Description |
|----------|-------------|
| **GOOGLE_OAUTH_CLIENT_ID** | Client ID ending in `.apps.googleusercontent.com` |
| **GOOGLE_OAUTH_CLIENT_SECRET** | Client secret |

**Apple Developer** — step-by-step: **`docs/APPLE_SIGN_IN_SETUP.md`**.

- **Return URL (exact):** `https://www.lumo22.com/api/auth/oauth/apple/callback`
- You need an **App ID** with Sign in with Apple, a **Services ID** (web client id), a **Key** (.p8), and **domain verification** for `www.lumo22.com` when Apple asks.

| Variable | Description |
|----------|-------------|
| **APPLE_OAUTH_CLIENT_ID** | **Services ID** identifier (e.g. `com.lumo22.web`) — alias **APPLE_CLIENT_ID** |
| **APPLE_OAUTH_TEAM_ID** | Team ID — alias **APPLE_TEAM_ID** |
| **APPLE_OAUTH_KEY_ID** | Key ID — alias **APPLE_KEY_ID** |
| **APPLE_OAUTH_PRIVATE_KEY** | Full `.p8` PEM (use `\n` for newlines in Railway), **or** prefer **APPLE_OAUTH_PRIVATE_KEY_B64** (base64 of the file — see doc) |

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
