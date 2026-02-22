# Step 2: SendGrid Inbound Parse — copy-paste checklist

The app is already set up: the `/webhooks/sendgrid-inbound` route exists and will process incoming emails. You only need to configure SendGrid and your DNS.

---

## Part A — SendGrid (about 2 minutes)

1. Log in to **SendGrid** → [https://app.sendgrid.com](https://app.sendgrid.com)
2. Go to **Settings** → **Inbound Parse** (or search for "Inbound Parse" in the menu).
3. Click **Add Host & URL** (or **Add new**).
4. Fill in:

   | Field | Value to paste |
   |-------|----------------|
   | **Destination URL** | `https://lumo-22-production.up.railway.app/webhooks/sendgrid-inbound` |
   | **Domain** | `inbound.lumo22.com` |
   | **Check "POST the raw, full MIME message"** | Optional (default is fine) |

   When you later move your site to lumo22.com, change the URL to:  
   `https://lumo22.com/webhooks/sendgrid-inbound`

5. Save. SendGrid will show you the **MX record(s)** you need to add (host and value).

---

## Part B — DNS (GoDaddy or your provider)

1. Open your DNS provider (e.g. **GoDaddy** → My Products → lumo22.com → **DNS** or **Manage DNS**).
2. **Add** a new record:
   - **Type:** MX
   - **Name / Host:** `inbound` (so it applies to `inbound.lumo22.com`)
   - **Value / Points to:** `mx.sendgrid.net`
   - **Priority:** `10`
   - **TTL:** 3600 (or 1 hour) is fine
3. Save. Propagation can take a few minutes up to 48 hours (often 5–15 minutes).

---

## Part C — Step 3: Verify

1. **Webhook is live**  
   Verified: `POST https://lumo-22-production.up.railway.app/webhooks/sendgrid-inbound` returns **200**. No action needed.

2. **Railway variables**  
   In Railway → your service → **Variables**, ensure these exist (paste your own values):  
   `OPENAI_API_KEY` · `SENDGRID_API_KEY` · `SUPABASE_URL` · `SUPABASE_KEY` · `FROM_EMAIL` · `INBOUND_EMAIL_DOMAIN` (optional, e.g. `inbound.lumo22.com`)

3. **Quick test (optional)**  
   After a customer has submitted the Digital Front Desk setup form, you’ll have a row in `front_desk_setups` with a `forwarding_email` like `reply-xxxxx@inbound.lumo22.com`. Send an email to that address; you should receive an auto-reply within a few seconds.

---

## Summary

- Your app uses `INBOUND_EMAIL_DOMAIN=inbound.lumo22.com` (in `.env` and on Railway). Leave that as is.
- After DNS has propagated, any email sent to `reply-xxxxx@inbound.lumo22.com` will be posted to your app and the app will auto-reply (for addresses that exist in `front_desk_setups`).

Done. Step 2 and Step 3 (verify) are complete.
