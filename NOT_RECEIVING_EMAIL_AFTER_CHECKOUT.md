# Not receiving the intake email after checkout

Follow these checks in order. They tell you exactly where the flow is failing.

---

## 1. Check Stripe webhook response

After a test payment:

1. **Stripe Dashboard** → **Developers** → **Webhooks** → click your endpoint (URL like `https://lumo-22-production.up.railway.app/webhooks/stripe`).
2. Open **Recent events** and find the **checkout.session.completed** event for your payment (match the time).
3. Click that event and look at **Response** / **Response code**.

| Response | Meaning |
|----------|--------|
| **200** | Your app accepted the webhook. The problem is later (payment not treated as captions, or SendGrid). Go to step 2. |
| **400** | Invalid signature. **STRIPE_WEBHOOK_SECRET** on Railway does not match Stripe’s **Signing secret**. Fix: [STEP_2_WEBHOOK_SECRET_DETAIL.md](STEP_2_WEBHOOK_SECRET_DETAIL.md). |
| **500** | Your app crashed handling the webhook. Check Railway logs (step 2) for the error. |
| **No event** | Stripe isn’t sending to this URL. Set **Endpoint URL** to `https://lumo-22-production.up.railway.app/webhooks/stripe` and ensure **checkout.session.completed** is in **Events to send**. |

---

## 2. Check Railway logs

1. **Railway** → your Lumo 22 service → **Deployments** → latest deployment → **View logs**.
2. Do **one more test payment** so the event is recent.
3. In the logs, search for **Stripe webhook** (or scroll to the time of the payment).

You should see lines like:

- `[Stripe webhook] event type=checkout.session.completed`
- `[Stripe webhook] checkout.session.completed amount_total=9700 ... _is_captions_payment=True`
- `[Stripe webhook] Customer email from session: your@email.com`
- `[Stripe webhook] Order created id=... token=...`
- `[SendGrid] Email sent OK ... to=your@email.com`

**What you see vs what to do:**

| Log line | Meaning |
|----------|--------|
| **`_is_captions_payment=False`** | Payment wasn’t treated as 30 Days Captions (e.g. different price). Check **STRIPE_CAPTIONS_PRICE_ID** and that you’re using the same product in Stripe. |
| **`No customer email in session`** | Stripe didn’t send the customer’s email. Ensure the customer entered an email on Stripe’s checkout page. |
| **`Failed to create order in Supabase`** | Supabase error. Check **SUPABASE_URL** and **SUPABASE_KEY** on Railway; ensure `caption_orders` table exists. |
| **`[SendGrid] Email NOT sent (no API key)`** | **SENDGRID_API_KEY** missing or empty on Railway. |
| **`[SendGrid] Error sending email`** | SendGrid rejected the send (e.g. **FROM_EMAIL** not verified, invalid key). Check the error text in the log. |
| **No `[Stripe webhook]` lines** | Stripe didn’t hit your app, or logs are from before the payment. Confirm step 1 (webhook URL and response). |

---

## 3. Confirm webhook URL and secret

- In the browser open: **https://lumo-22-production.up.railway.app/webhooks/stripe**  
  You should see: `{"configured": true}`. If **configured** is `false`, set **STRIPE_WEBHOOK_SECRET** on Railway (see [STEP_2_WEBHOOK_SECRET_DETAIL.md](STEP_2_WEBHOOK_SECRET_DETAIL.md)).

---

## 4. Send a test intake email (same path as real one)

From your project folder:

```bash
python3 send_test_intake_email.py your@email.com
```

Use the same email you use for test payments. If this email **does** arrive, SendGrid is working and the issue is earlier (webhook, secret, or payment detection). If it **does not** arrive, fix SendGrid (API key, **FROM_EMAIL**, domain authentication).

---

## 5. Check spam and address

- Check the **spam/junk** folder for the address you used at checkout.
- Ensure you’re checking the **exact email** you entered on the Stripe checkout page (not a different inbox).

---

**Quick checklist**

- [ ] Stripe webhook event **response code** is 200  
- [ ] Railway logs show `[Stripe webhook] ... _is_captions_payment=True`  
- [ ] Railway logs show `Customer email from session: your@email.com`  
- [ ] Railway logs show `[SendGrid] Email sent OK`  
- [ ] **STRIPE_WEBHOOK_SECRET** on Railway matches Stripe’s Signing secret (starts with `whsec_`)  
- [ ] **SENDGRID_API_KEY** and **FROM_EMAIL** are set on Railway  
- [ ] Test script email arrives when you run `send_test_intake_email.py your@email.com`

For more detail (including how to get the Signing secret and set Railway variables), see [DEBUG_NO_INTAKE_EMAIL.md](DEBUG_NO_INTAKE_EMAIL.md).
