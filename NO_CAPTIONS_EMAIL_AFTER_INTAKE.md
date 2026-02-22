# Completed the intake form but didn't receive the 30 Days Captions email

After you submit the intake form, a background job generates your captions with OpenAI and emails you **30_Days_Captions.md**. If that email never arrives, check the following.

---

## 1. Check Railway logs

1. **Railway** → your Lumo 22 service → **Deployments** → **View logs**.
2. Submit the intake form again (use the same intake link from your order email, or a new test order).
3. In the logs, search for **`[Captions]`**.

**What you should see:**

- `[Captions] Starting generation for order ...` — Intake was saved and the job started.
- `[Captions] Calling OpenAI for order ...` — OpenAI request is running.
- `[Captions] Sending delivery email to ...` — About to send the email.
- `[Captions] Delivery email sent for order ...` — Email was sent. Check inbox and spam.

**If you see an error:**

- `[Captions] Generation or delivery failed for order ...: OPENAI_API_KEY not configured`  
  → Set **OPENAI_API_KEY** in Railway Variables (from [OpenAI API keys](https://platform.openai.com/api-keys)). Redeploy.
- `[Captions] Generation or delivery failed ...: Invalid header value` or similar  
  → **OPENAI_API_KEY** or **SENDGRID_API_KEY** may have a newline in Railway. Edit the variable, delete the value, paste it again with no line break, save, redeploy.
- `[Captions] Delivery email FAILED`  
  → SendGrid rejected the send. Check **SENDGRID_API_KEY** and **FROM_EMAIL** in Railway; see **DOMAIN_AUTH_CHECKLIST.md** for deliverability.
- No `[Captions]` lines at all  
  → Intake submit may have failed (wrong token, or request didn’t reach the server). Try again with the link from your order email.

---

## 2. Check your spam folder

The delivery email comes from **FROM_EMAIL** (e.g. hello@lumo22.com). Check spam/junk for that sender and for subject **"Your 30 Days of Social Media Captions"**.

---

## 3. Confirm Railway variables

For caption generation and delivery you need:

- **OPENAI_API_KEY** — From OpenAI. No spaces or newlines.
- **SENDGRID_API_KEY** — From SendGrid. No spaces or newlines.
- **FROM_EMAIL** — Verified sender in SendGrid (e.g. hello@lumo22.com).
- **SUPABASE_URL** and **SUPABASE_KEY** — So the order and intake are stored and the job can run.

Redeploy after changing any variable.

---

## 4. See the error in your browser (after you’ve submitted the form once)

After you’ve submitted the intake form at least once, open this URL in your browser (replace `YOUR_TOKEN` with the token from your intake link):

**https://lumo-22-production.up.railway.app/api/captions-deliver-test?t=YOUR_TOKEN**

To get YOUR_TOKEN: open the intake link from your order email. It looks like  
`https://.../captions-intake?t=abc123xyz...` — the part after `t=` is your token. Copy it and put it in the URL above after `t=`.

This runs generation + delivery **synchronously** and returns JSON:

- **`{"ok": true, "message": "..."}`** — It worked. Check your email (and spam).
- **`{"ok": false, "error": "the actual error message"}`** — That `error` is the cause (e.g. OPENAI_API_KEY not configured, SendGrid failed). Fix that and try again.

---

## 5. Run a quick test (same flow as real order)

From your project folder:

```bash
python3 test_webhook_handler.py your@email.com
```

Then open the intake link from that email, fill the form, and submit. Check Railway logs for `[Captions]` and the delivery email.

---

**Summary:** The usual causes are missing **OPENAI_API_KEY** on Railway, or a newline in **OPENAI_API_KEY** / **SENDGRID_API_KEY**. Fix the variable(s), redeploy, then submit the intake again and watch the logs for `[Captions]`.
