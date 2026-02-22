# Step 2 in detail: Check the webhook secret (Railway)

Your app uses **STRIPE_WEBHOOK_SECRET** to verify that incoming webhook requests really come from Stripe. If this value doesn’t match the **Signing secret** Stripe shows for your endpoint, Stripe gets **400 Invalid signature** and your app never processes the event — so no intake email is sent.

Do both parts below: get the secret from Stripe, then set it in Railway.

---

## Part A: Get the Signing secret from Stripe

1. **Open Stripe**
   - Go to **https://dashboard.stripe.com** and log in.
   - Make sure you’re in **Test mode** or **Live mode** depending on how you’re testing (toggle in the top right if you see it).

2. **Open Webhooks**
   - In the left sidebar, click **Developers**.
   - Then click **Webhooks** (or **Webhook endpoints**).

3. **Find your Lumo 22 endpoint**
   - You should see at least one endpoint. Its **Endpoint URL** will look like:
     - `https://lumo-22-production.up.railway.app/webhooks/stripe`
     - or your custom domain, e.g. `https://lumo22.com/webhooks/stripe`
   - Click that **endpoint** (the URL or the row) to open its details.

4. **Open Signing secret**
   - On the endpoint details page, find **Signing secret** (sometimes under “Signing secret” or “Webhook signing secret”).
   - It’s hidden by default. Click **Reveal** (or “Click to reveal”).
   - The value starts with **`whsec_`** and is a long string (e.g. `whsec_abc123...`).

5. **Copy the secret**
   - Select the whole value (from `whsec_` to the end).
   - Copy it (Ctrl+C / Cmd+C).
   - **Don’t** add spaces, quotes, or line breaks. Paste it somewhere safe (e.g. Notepad) to double‑check: it should be one line, starting with `whsec_`.

---

## Part B: Set STRIPE_WEBHOOK_SECRET in Railway

1. **Open Railway**
   - Go to **https://railway.app** and log in.
   - Open the **project** that has your Lumo 22 app.
   - Click the **service** (e.g. “Lumo 22”) that runs the app.

2. **Open Variables**
   - Click the **Variables** tab (or **Settings** → **Variables**, depending on the layout).
   - You’ll see a list of environment variables (e.g. `BASE_URL`, `SENDGRID_API_KEY`, etc.).

3. **Find or add STRIPE_WEBHOOK_SECRET**
   - **If STRIPE_WEBHOOK_SECRET is already there:**  
     Click it to edit. Delete the current value and **paste the Signing secret you copied from Stripe** (the full `whsec_...` string).  
   - **If it’s not there:**  
     Click **Add variable** (or **New variable**).  
     - **Name:** `STRIPE_WEBHOOK_SECRET` (exactly, all caps, underscores).  
     - **Value:** paste the Signing secret from Stripe (the full `whsec_...` string).

4. **Paste rules**
   - **No quotes** — paste only the raw value, e.g. `whsec_abc123xyz...`.
   - **No spaces** — no space before `whsec_` or after the last character.
   - **One line** — the whole secret on a single line.
   - **Same mode** — if you test with Stripe **Test mode**, use the Signing secret from the webhook endpoint you use in Test mode. If you use a **Live** endpoint, use that endpoint’s Signing secret.

5. **Save**
   - Save the variable (e.g. **Save** or **Update**). Railway will redeploy your app with the new value. Wait for the deployment to finish (usually 1–2 minutes).

---

## Check it worked

1. **Stripe:** Developers → Webhooks → your endpoint → **Recent events**. Trigger a test event or do another test payment.
2. **Stripe:** Click the latest **checkout.session.completed** event. Under **Response**, you want **200** (not 400).
3. **Railway:** Your service → **Deployments** → latest deployment → **View logs**. Look for:
   - `[Stripe webhook] event type=checkout.session.completed`
   - then either the intake email log or an error.

If you still get **400 Invalid signature** after this, the value in Railway is still different from the Signing secret in Stripe — copy it again from Stripe (Reveal → copy full string) and set it again in Railway with no extra characters.
