# Where to see the real "Handler failed" error

Stripe only shows `{"error": "Handler failed"}`. The **actual** error is in your app.

---

## Your app runs on Railway (not your laptop)

When you do a **test order** on the live site, the webhook runs on **Railway**, not in your local terminal. So:

- **"Flask server logs"** = **Railway deploy logs**
- You won’t see anything in your local terminal for that request.

---

## Option A: See the error in your terminal (recommended)

Run the same steps as the webhook **locally** so the traceback appears in your terminal:

```bash
python3 test_webhook_handler.py skoverment@gmail.com
```

(Use the same email you use for test orders.)

- If it **fails**, you’ll see the real error and traceback. That’s the same error causing 500 on Railway.
- If it **succeeds**, Supabase and SendGrid are OK locally; the problem may be env vars or config that differ on Railway.

---

## Option B: See the error in your browser (on Railway)

After you **redeploy**, open this URL in your browser:

**https://lumo-22-production.up.railway.app/api/captions-webhook-test**

It runs the same steps as the webhook (create order + send email) and returns JSON:

- **`{"ok": true, "message": "..."}`** — Webhook logic works on Railway; the 500 may be from the real Stripe payload (we can debug that next).
- **`{"ok": false, "error": "the actual error message"}`** — That `error` text is the real cause. Fix that (e.g. Supabase, SendGrid) and the webhook should stop returning 500.

You can pass an email to use: `?email=skoverment@gmail.com` (optional).

---

## Option C: See the error in Railway logs

1. **Railway** → your project → **Lumo 22** service.
2. **Deployments** → latest deployment → **View logs** (or **Deploy logs**).
3. Do **one more test order** (or resend the webhook in Stripe).
4. In the logs, search for **`[Stripe webhook]`** or **`FAILED`** or **`Traceback`**.
5. The line after **`captions handler error:`** (or the traceback) is the real error.

---

## Option D: See the error in Stripe’s response body

After the latest deploy, the webhook returns a **`detail`** field on 500:

```json
{"error": "Handler failed", "detail": "Supabase configuration missing"}
```

In **Stripe** → **Developers** → **Webhooks** → your endpoint → **Recent events** → click the failed event → **Response body**. If you see **`detail`**, that’s the error message.

---

## What to do with the error

| Error (example) | Fix |
|-----------------|-----|
| **Supabase configuration missing** | Set **SUPABASE_URL** and **SUPABASE_KEY** in Railway → Variables. |
| **Failed to create caption order** / **permission denied** / **row-level security** | Run [database_caption_orders.sql](database_caption_orders.sql) and [database_caption_orders_rls.sql](database_caption_orders_rls.sql) in Supabase SQL Editor. |
| **Email NOT sent (no API key)** | Set **SENDGRID_API_KEY** and **FROM_EMAIL** in Railway → Variables. |
| **Invalid non-printable ASCII** | Re-type **BASE_URL** and **FROM_EMAIL** in Railway Variables (no newlines, no spaces). |

Run **Option A** first; paste the traceback or `detail` here and we can fix it.

---

## If the local test passed but Railway still returns 500

Then Supabase and SendGrid work with your `.env`. Railway is using different or broken env vars.

**Do this:**

1. In **Railway** → **Lumo 22** → **Variables**, ensure these are set **exactly** as in your `.env` (copy-paste, no extra spaces or newlines):
   - **SUPABASE_URL**
   - **SUPABASE_KEY**
   - **SENDGRID_API_KEY**
   - **FROM_EMAIL**
2. For **BASE_URL**, type: `https://lumo-22-production.up.railway.app` (no trailing slash, no line break).
3. Save variables (Railway will redeploy).
4. Trigger the webhook again (Resend in Stripe or a new test order).

If it still fails, open **Option B** (the webhook-test URL) in your browser to see the error, or check **Railway deploy logs** (Option C) for the line `[Stripe webhook] captions handler error:` and the traceback below it.
