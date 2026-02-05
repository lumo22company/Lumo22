# No email after buying Digital Front Desk

If you don’t receive the setup email after paying for Digital Front Desk, check the following.

## 1. Stripe webhook is firing

- **Stripe Dashboard** → **Developers** → **Webhooks** → your endpoint (e.g. `https://your-domain.com/webhooks/stripe`).
- Open **Recent deliveries** and find the `checkout.session.completed` event for your test payment.
- If the response is **200**, the app received the event. If it’s **4xx/5xx**, the app rejected it — check the response body and your Railway logs.

## 2. Railway logs

After a test payment, in **Railway** → your service → **Deployments** → **View logs**, look for:

- `[Stripe webhook] checkout.session.completed amount_total=...` — confirms the event was received.
- `[Stripe webhook] Front Desk: no customer email` — email was missing from the session (see step 3).
- `[Stripe webhook] Front Desk: amount=... not in (7900, 14900, 29900)` — payment wasn’t recognised as a Front Desk plan (e.g. wrong currency or amount).
- `[Stripe webhook] Sending Front Desk setup email to ...` and `... setup email sent` — email was sent.
- `[Stripe webhook] Front Desk setup email FAILED` — SendGrid rejected the send (see step 4).

## 3. Customer email in the session

The webhook uses the checkout session’s **customer_details** (or fetches the session from Stripe if needed). If you see “no customer email” in the logs:

- In Stripe, ensure the Payment Link (or Checkout) **collects email**.
- In **Stripe** → **Developers** → **Webhooks** → your endpoint → **Update details** → under “Events to send”, ensure **checkout.session.completed** is selected. Optionally add **customer_details** in “Listen for events on” if your Stripe version allows it (otherwise the app will fetch the session with `expand=["customer_details"]`).

## 4. SendGrid

- **Railway Variables:** `SENDGRID_API_KEY` and `FROM_EMAIL` must be set. `FROM_EMAIL` should be a verified sender in SendGrid (e.g. `hello@lumo22.com`).
- If logs show “Front Desk setup email FAILED”, check SendGrid **Activity** for the recipient address and the reason (bounce, invalid API key, etc.).

## 5. Success URL for Digital Front Desk

Keep the **success URL** for your **Digital Front Desk** Payment Links (Starter, Standard, Premium) as:

- `https://your-domain.com/activate-success`

Do **not** use `/website-chat-success` for Front Desk — that’s only for the **Website Chat Widget** (£59) product.

---

After fixing, run another test payment and watch the logs; you should see the setup email sent and receive it at the address you used at checkout.
