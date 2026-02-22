# Why you're not receiving captions emails — how to check

Both the **intake-link email** (after payment) and the **delivery email** (after you submit the form) are sent via **SendGrid**. If you have the correct keys in `.env` and Railway but still don't get emails, use these checks.

---

## 1. Verify the sender (FROM_EMAIL) in SendGrid

SendGrid only sends from **verified** senders. If `FROM_EMAIL` (e.g. `hello@lumo22.com`) is not verified, SendGrid may accept the request but not deliver, or return an error.

1. Go to **SendGrid** → **Settings** → **Sender Authentication** (or **Sender identities** / **Single Sender Verification**).
2. Check that **hello@lumo22.com** (or whatever is in `FROM_EMAIL`) is listed and **Verified**.
3. If not: add it as a **Single Sender**, complete the verification (click the link in the email SendGrid sends), and wait until it shows Verified.

If you use a custom domain (e.g. lumo22.com), you may need **Domain Authentication** instead; follow SendGrid’s steps for that.

---

## 2. Check Railway deploy logs

After a test payment and/or intake submit, look at **Railway** → your service → **Deployments** → latest deployment → **Deploy logs** (or **View logs**).

Look for lines like:

- **Intake-link email:**  
  `[SendGrid] Email sent OK ...` or  
  `[SendGrid] Email NOT sent (no API key)` or  
  `[SendGrid] Error sending email to ...` or  
  `Stripe captions webhook: intake-link email FAILED to send to ...`

- **Delivery email:**  
  `[SendGrid] Email with attachment sent OK ...` or  
  `[SendGrid] Error sending email with attachment to ...` or  
  `Caption delivery email FAILED for order ...`

- If you see **no API key**: `SENDGRID_API_KEY` is missing or empty in Railway Variables.
- If you see **Error sending email** or **rejected (status=...)** copy the full line; the status code and message explain why SendGrid refused (e.g. unverified sender, invalid from, rate limit).

---

## 3. Check SendGrid Activity

SendGrid logs every send attempt.

1. Go to **SendGrid** → **Activity** (or **Email Activity**).
2. Filter by the last hour (or the time of your test).
3. Look for events to the address you used to pay / submit intake.

You might see:

- **Delivered** — email was accepted by the recipient server (check spam if you don’t see it).
- **Deferred** / **Bounce** / **Blocked** — click the event for the reason (e.g. invalid address, spam filter, unverified sender).
- **Processed** but not **Delivered** — often means the receiving server rejected it; the event details usually say why.

If there are **no** events for your test email, the app likely never called SendGrid (e.g. webhook not received, or an exception before `send_email`). In that case the Railway logs (step 2) will show what happened.

---

## 4. Quick checklist

- [ ] **FROM_EMAIL** in Railway matches the **verified** sender in SendGrid (e.g. `hello@lumo22.com`).
- [ ] **SENDGRID_API_KEY** in Railway is the full key (starts with `SG.`), no extra spaces or quotes.
- [ ] **Stripe webhook** is hitting your app: in Stripe → Developers → Webhooks → your endpoint → recent events, check for `checkout.session.completed` and that the request succeeded (200). If Stripe gets 500 or timeout, the intake email might not be sent.
- [ ] **Spam/junk** folder for the email address you used.
- [ ] After redeploying with the new logging, run **one** test payment and **one** intake submit, then check Railway logs and SendGrid Activity for that time.

---

## 5. Test SendGrid from your machine (optional)

To confirm the key and sender work, you can run a one-off script that sends a test email using the same `NotificationService` (and thus the same `FROM_EMAIL` and SendGrid key from `.env`). If that fails, the error message will point to the cause (e.g. unverified sender, invalid API key).

If you want, I can add a small script `test_sendgrid.py` that sends one email to an address you choose and prints success or the error.
