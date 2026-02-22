# Why you're not receiving the intake email after a test buy

The **automation and intake form are already built**. After payment, Stripe calls your webhook → your app creates the order and sends the intake email. If you're not getting the email, one of these is wrong.

---

## 1. Check Stripe webhook is reaching your app

1. Go to **Stripe Dashboard** → **Developers** → **Webhooks**.
2. Click your **webhook endpoint** (the one pointing to your Railway URL).
3. Check **Recent events** (or **Event log**). Find the **checkout.session.completed** event for your test payment.
4. Click it. Look at **Response**:
   - **200** = your app received it and responded OK. Go to step 2.
   - **4xx or 5xx** = your app rejected it or crashed. Note the status (e.g. 400 = bad request, 500 = server error). Then check **Railway deploy logs** (step 3) for the error.

**Webhook URL must be exactly:**  
`https://lumo-22-production.up.railway.app/webhooks/stripe`  
(Use your real Railway URL if different. No trailing slash.)

---

## 2. Check the webhook secret (Railway)

If Stripe got **400 Invalid signature**, the **Signing secret** Stripe uses doesn't match what your app has.

1. **Stripe** → Developers → Webhooks → your endpoint → **Signing secret** (click Reveal). Copy it (starts with `whsec_`).
2. **Railway** → your service → **Variables** → **STRIPE_WEBHOOK_SECRET**. It must be **exactly** that value (no spaces, no quote marks).
3. Save and redeploy if you change it.

---

## 3. Check Railway deploy logs

After a test payment, open **Railway** → your service → **Deployments** → latest → **View logs** (or **Deploy logs**).

Look for lines like:

- **`[Stripe webhook] event type=checkout.session.completed`** — Stripe hit your app.
- **`[Stripe webhook] checkout.session.completed amount_total=9700 ... _is_captions_payment=True`** — App treated it as a captions payment and ran the handler.
- **`[SendGrid] Email sent OK ... to=your@email.com`** — Intake email was sent.
- **`[SendGrid] Error sending email ...`** or **`intake-link email FAILED`** — Email failed (e.g. SendGrid key, from address).
- **`_is_captions_payment=False`** — Payment didn’t match (e.g. wrong amount or no metadata). For **£97** the amount must be **9700** (pence). If you used a different price or currency, the handler won’t run.

So: **No webhook lines** → Stripe isn’t calling your URL or secret is wrong. **Webhook lines but _is_captions_payment=False** → amount/metadata mismatch. **Webhook + True but Email FAILED** → SendGrid/sender issue.

---

## 4. Quick checklist

- [ ] **Stripe webhook URL** = `https://YOUR-RAILWAY-URL/webhooks/stripe` (e.g. lumo-22-production.up.railway.app).
- [ ] **Stripe** → Webhooks → your endpoint → **Events to send** includes **checkout.session.completed**.
- [ ] **Railway** → **STRIPE_WEBHOOK_SECRET** = the **Signing secret** from that Stripe endpoint (starts with `whsec_`).
- [ ] **Railway** → **SENDGRID_API_KEY** and **FROM_EMAIL** are set (for sending the intake email).
- [ ] **BASE_URL** on Railway = your Railway URL (no trailing slash) so the intake link in the email is correct.

---

## 5. What’s already built (no need to rebuild)

- **Stripe webhook** → On `checkout.session.completed` we create the order and send the intake email.
- **Intake form** → `/captions-intake?t=TOKEN` (link in that email). Customer fills it and submits.
- **Intake API** → Saves answers, runs caption generation, sends delivery email with the captions file.

Once the webhook and SendGrid are correct, the intake email will arrive and the rest of the flow will work.
