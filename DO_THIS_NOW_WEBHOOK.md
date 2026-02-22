# Do this now: set the webhook secret so intake emails work

You only need to do **two things**: copy the secret from Stripe, then paste it in Railway.

---

## 1. Get the secret from Stripe (about 1 minute)

1. Open: **https://dashboard.stripe.com/webhooks**  
   (If it asks you to log in, log in.)

2. Click your webhook endpoint (the one whose URL is `https://lumo-22-production.up.railway.app/webhooks/stripe` or your domain).

3. Under **Signing secret**, click **Reveal**.  
   You’ll see a value that starts with **`whsec_`**.

4. Click **Reveal** and copy the **entire** value (from `whsec_` to the end).  
   Paste it into Notepad or any text editor to double-check: one line, no spaces, no quotes.

---

## 2. Put it in Railway (about 1 minute)

1. Open: **https://railway.app**  
   Log in → open your project → click the **Lumo 22** service.

2. Go to the **Variables** tab.

3. Find **STRIPE_WEBHOOK_SECRET**:
   - If it exists: click it, delete the old value, and paste the value you copied from Stripe.
   - If it doesn’t exist: click **+ New variable**, name it **STRIPE_WEBHOOK_SECRET**, value = the pasted secret.

4. Save. Railway will redeploy (wait 1–2 minutes).

---

## 3. Check it worked

From your project folder run:

```bash
python3 check_webhook_setup.py
```

You should see: **OK — Webhook endpoint is reachable and STRIPE_WEBHOOK_SECRET is set.**

If the script can’t reach your site (e.g. custom domain not ready), use the Railway URL explicitly:

```bash
BASE_URL=https://lumo-22-production.up.railway.app python3 check_webhook_setup.py
```

If you see **NOT SET**, the variable didn’t save correctly — paste the secret again in Railway (no quotes, no spaces, one line).

---

## DFD / Chat: disable widget when subscription cancelled

If you sell DFD (Digital Front Desk) or Chat subscriptions, ensure your Stripe webhook listens for **`customer.subscription.deleted`** so the chat widget stops working when customers cancel. In Stripe Dashboard → Webhooks → your endpoint → **Select events** → add `customer.subscription.deleted`.

---

**Direct links**

- Stripe webhooks: https://dashboard.stripe.com/webhooks  
- Railway variables: open your project → Lumo 22 service → **Variables** tab

For more detail (e.g. where exactly “Signing secret” is), see [STEP_2_WEBHOOK_SECRET_DETAIL.md](STEP_2_WEBHOOK_SECRET_DETAIL.md).
