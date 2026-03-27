# Force caption PDF delivery (when email still hasn’t arrived)

Do these **on your live site** after deploying the latest code (stuck orders are also retried automatically every **10 minutes** in production).

## 1. Check config (no secrets exposed)

Open in a browser:

`https://YOUR_DOMAIN/api/captions-delivery-status`

You need **`all_ok": true`**. If not:

- Set **`ANTHROPIC_API_KEY`** or **`OPENAI_API_KEY`** (matches **`AI_PROVIDER`**).
- Set **`SENDGRID_API_KEY`** and a verified **`FROM_EMAIL`** in SendGrid.

## 2. Force one order to generate + email (strongest fix)

### Option A — script (easiest locally)

1. In Railway → Variables, set **`CAPTIONS_DELIVER_TEST_SECRET`** (e.g. `openssl rand -hex 32`), redeploy.
2. From the project root:

```bash
export BASE_URL=https://www.lumo22.com
export CAPTIONS_DELIVER_TEST_SECRET='paste-the-same-value'
export INTAKE_TOKEN='paste-token-from-captions-intake-url'
./scripts/force_caption_delivery.sh
```

(Or put `BASE_URL`, `CAPTIONS_DELIVER_TEST_SECRET`, and `INTAKE_TOKEN` in `.env` and run the script — it loads `.env`.)

### Option B — `curl`

1. In Railway (or your host), set **`CAPTIONS_DELIVER_TEST_SECRET`** to a long random string (e.g. `openssl rand -hex 32`).
2. From the intake link, copy the **`t=`** token from the address bar.
3. Run (replace placeholders; **`sync=1`** waits for the real result — can take **1–3 minutes**):

```bash
curl -sS -m 320 "https://YOUR_DOMAIN/api/captions-deliver-test?t=YOUR_TOKEN&secret=YOUR_SECRET&sync=1"
```

- **`"ok": true`** → check inbox + spam for **Your 30 Days of Social Media Captions**.
- **`"ok": false`** → read **`error`** (often SendGrid rejection or AI error). Fix env and run again.

Background mode (returns immediately; same as after form submit):

```bash
curl -sS "https://YOUR_DOMAIN/api/captions-deliver-test?t=YOUR_TOKEN&secret=YOUR_SECRET"
```

## 3. Optional: run recovery + reminders cron manually

If you use **`CRON_SECRET`**:

```bash
curl -sS "https://YOUR_DOMAIN/api/captions-send-reminders?secret=YOUR_CRON_SECRET"
```

Check JSON for **`stuck_first_delivery_triggered`** (orders that were picked up for retry).

## 4. In Supabase

Open **`caption_orders`** for your email:

- **`status`**: `delivered` = success; **`failed`** = generation or email failed (see Railway logs for `[Captions]` / `[SendGrid]`).
- If intake exists but **`captions_md`** is empty and status stuck, the **10‑minute scheduler** or **`captions-send-reminders`** should retry (or use step 2).
