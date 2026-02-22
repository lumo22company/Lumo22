# Still no email after payment — run this and report back

Do these **in order** and note what you see. That will show where the flow is failing.

---

## 1. Confirm the webhook URL is reachable

In your browser, open:

**https://lumo-22-production.up.railway.app/webhooks/stripe**

You should see JSON like: `{"message": "Stripe webhook endpoint...", "configured": true}`.

- If you see that and **"configured": true** → the app is up and the secret is set on Railway. Go to step 2.
- If you get an error or "The train has not arrived" → the app isn’t running or the URL is wrong; fix that first.
- If **"configured": false** → **STRIPE_WEBHOOK_SECRET** is missing or empty on Railway. Add it (Step 2 in STEP_2_WEBHOOK_SECRET_DETAIL.md).

---

## 2. What does Stripe say after your test payment?

1. Go to **Stripe Dashboard** → **Developers** → **Webhooks**.
2. Click your endpoint (the one pointing to your Railway URL).
3. Open **Recent events** (or **Event log**).
4. Find the **checkout.session.completed** event for your test payment (match the time).
5. Click that event.
6. Look at **Response** (or **Response code**).

**What is the response code?**

- **200** → Your app accepted the webhook. The problem is either “not treated as captions” or “SendGrid failed”. Go to step 3.
- **400** → Invalid signature. The **Signing secret** in Stripe does not match **STRIPE_WEBHOOK_SECRET** on Railway. Copy the secret from Stripe again (Reveal) and set it in Railway; redeploy.
- **500** → Your app crashed handling the webhook. Check Railway logs (step 3) for the error.
- **No event / never received** → Stripe isn’t sending to this URL. Check the webhook **Endpoint URL** is exactly `https://lumo-22-production.up.railway.app/webhooks/stripe` and that **Events to send** includes **checkout.session.completed**.

---

## 3. What do Railway logs show?

1. Go to **Railway** → your service → **Deployments** → latest deployment.
2. Open **View logs** (or **Deploy logs**).
3. Do **one more test payment** (so the event is recent).
4. In the logs, search for **Stripe webhook** (or scroll to the time of the payment).

**What do you see?**

- **`[Stripe webhook] event type=checkout.session.completed`**  
  → Stripe hit your app.

- **`[Stripe webhook] checkout.session.completed amount_total=9700 ... _is_captions_payment=True`**  
  → Your app treated it as a captions payment and ran the handler.

- **`[SendGrid] Email sent OK ... to=your@email.com`**  
  → The intake email was sent. Check inbox and spam for that address.

- **`_is_captions_payment=False`** or **amount_total=...** with something other than 9700  
  → Payment didn’t match (e.g. different price or currency). Tell me the **amount_total** you see and we can add that amount to the check.

- **`[SendGrid] Error sending email`** or **`intake-link email FAILED`**  
  → SendGrid failed (e.g. key, from address). The log line should have the error; fix SendGrid on Railway.

- **No `[Stripe webhook]` lines at all**  
  → Either Stripe didn’t call your app (check step 2) or logs are from before the payment; do another payment and check again.

---

## 4. Send a test intake email (same path as real one)

This sends one intake email using the same code path as the webhook, so you can confirm SendGrid and the link work.

From your project folder:

```bash
python3 send_test_intake_email.py your@email.com
```

(Use the email you use for test payments.) Check that address for the intake email and that the link opens the intake form.

---

**Reply with:**

1. Step 1: What you saw at `/webhooks/stripe` (and whether `configured` was true).
2. Step 2: Stripe webhook event **response code** (200, 400, 500, or “no event”).
3. Step 3: The **exact** `[Stripe webhook]` and any `[SendGrid]` lines from Railway logs around the time of the test payment (or “no Stripe webhook lines”).
4. Step 4: Whether the test intake email arrived and the link worked.

With that we can see whether the problem is: URL, secret, payment detection (amount), or SendGrid.
