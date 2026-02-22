# 30 Days Captions — Go live checklist

Do these in order. Only you can do them (Stripe/Railway logins, test payment).

---

## Before you start

- [ ] **Railway Variables** are set (see **RAILWAY_VARIABLES_LIST.md**), including `STRIPE_WEBHOOK_SECRET` and `BASE_URL`.
- [ ] **Redirect to intake after payment:** Add `STRIPE_SECRET_KEY` and `STRIPE_CAPTIONS_PRICE_ID` (see RAILWAY_VARIABLES_LIST.md). Then after payment, customers are sent straight to the intake form.
- [ ] If your Railway URL shows **“The train has not arrived at the station”**, fix that first: see **TROUBLESHOOT_RAILWAY_TRAIN.md** (check deployment logs and set **Start Command** to `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`).

---

## 0. Stripe “After payment” redirect (fix “page not found”)

- [ ] In **Stripe** → **Product catalog** (or **Payment links**) → open the **payment link** you use for 30 Days Captions.
- [ ] Find **After payment** / **Confirmation page** / **Redirect URL**.
- [ ] Set it to **YOUR_RAILWAY_URL** + `/captions-thank-you`  
  Example: `https://lumo22-production-xxxx.up.railway.app/captions-thank-you`  
  **Not** lumo22.com unless that domain points to your Railway app.
- [ ] Save. Next payment will redirect to your thank-you page.

---

## 1. Stripe webhook URL

- [ ] Open **Stripe** → **Developers** → **Webhooks** (or **Destinations**).
- [ ] Open your Lumo 22 destination.
- [ ] Set **Endpoint URL** to: **YOUR_RAILWAY_URL** + `/webhooks/stripe`  
  Example: `https://lumo22-production-xxxx.up.railway.app/webhooks/stripe`  
  (Use the exact URL from Railway → your service → Settings → Networking.)
- [ ] Save.

---

## 2. BASE_URL in Railway

- [ ] Open **Railway** → your project → **"Lumo 22"** service → **Variables**.
- [ ] Check **BASE_URL** = your Railway URL with **no** slash at the end.  
  Example: `https://lumo22-production-xxxx.up.railway.app`
- [ ] If you change it, save (Railway will redeploy).

---

## 3. Test the full flow (Stripe test mode ON)

- [ ] In Stripe, turn **Test mode** on (top right).
- [ ] Open **YOUR_RAILWAY_URL/captions** in your browser.
- [ ] Click **Get my 30 days**. Pay with test card: `4242 4242 4242 4242`.
- [ ] You land on the thank-you page. If checkout is set up, you're redirected to the **intake form** within a few seconds; otherwise check your email for the intake link.
- [ ] Fill the intake form, click **Send my answers**.
- [ ] You get a **second email** with **30_Days_Captions.md** attached.

If any step fails, check Stripe webhook URL (step 1) and BASE_URL (step 2), then try again.

---

## 4. Go live (real payments)

- [ ] When you’re happy with the test, turn **Stripe test mode** off.
- [ ] In Railway Variables, **CAPTIONS_PAYMENT_LINK** must be your **live** Stripe payment link (not the test link).
- [ ] Share your captions page: **YOUR_RAILWAY_URL/captions**

---

## 5. Optional — Use lumo22.com

- [ ] Railway → your service → **Settings** → **Networking** → **Custom domain** → add `lumo22.com`.
- [ ] Follow the DNS instructions Railway shows.
- [ ] In Railway Variables, set **BASE_URL** = `https://lumo22.com`
- [ ] In Stripe, set webhook URL to `https://lumo22.com/webhooks/stripe`

---

**YOUR_RAILWAY_URL** = the URL from Railway → your service → Settings → Networking (e.g. `https://something.up.railway.app`).
