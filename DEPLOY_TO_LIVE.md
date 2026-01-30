# Deploy LUMO22 so lumo22.com (or your live URL) works

Your app runs on **port 5001** locally. To have it live at **lumo22.com** (or a host URL), deploy this repo to a host and set your env vars there. Below: **Railway** (simplest) and **Render**.

---

## Option A: Railway (good for getting live fast)

1. **Sign up:** [railway.app](https://railway.app) (log in with GitHub).

2. **New project:** Dashboard → **New Project** → **Deploy from GitHub repo**. Choose your LUMO22 repo (or push this folder to a GitHub repo first, then connect it).

3. **Env vars:** In the project, click your service → **Variables**. Add every variable from your `.env` (copy from your machine; don’t paste secrets here). At minimum you need:
   - `FLASK_ENV=production`
   - `SECRET_KEY=` (a long random string)
   - `OPENAI_API_KEY=`
   - `SUPABASE_URL=`
   - `SUPABASE_KEY=`
   - `SENDGRID_API_KEY=`
   - `FROM_EMAIL=hello@lumo22.com`
   - `CAPTIONS_PAYMENT_LINK=`
   - `STRIPE_WEBHOOK_SECRET=`
   - `BASE_URL=` (see step 4)

4. **BASE_URL:** After the first deploy, Railway gives you a URL like `https://lumo22-production.up.railway.app`. Set:
   - `BASE_URL=https://lumo22-production.up.railway.app`  
   (or your custom domain once you add it).  
   Then in **Stripe** → your webhook destination → edit the endpoint URL to this same `BASE_URL` + `/webhooks/stripe`, e.g. `https://lumo22-production.up.railway.app/webhooks/stripe`.

5. **Custom domain (optional):** In Railway → your service → **Settings** → **Domains** → **Custom Domain** → add `lumo22.com`. Follow the DNS instructions. Then set `BASE_URL=https://lumo22.com` and update the Stripe webhook URL to `https://lumo22.com/webhooks/stripe`.

6. **Start command:** Railway usually detects the **Procfile** in the repo. If it doesn’t, set the start command to:
   ```bash
   gunicorn -w 1 -b 0.0.0.0:$PORT app:app
   ```

7. Redeploy after changing env vars. Then test: open `BASE_URL/captions` and run through Step 7 (test payment → email → form → delivery).

---

## Option B: Render

1. **Sign up:** [render.com](https://render.com) (log in with GitHub).

2. **New Web Service:** Dashboard → **New** → **Web Service**. Connect your LUMO22 GitHub repo.

3. **Settings:**
   - **Runtime:** Python 3.
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`

4. **Env:** **Environment** tab → Add all variables from your `.env`. Include `BASE_URL` — after deploy Render gives you a URL like `https://lumo22.onrender.com`; set `BASE_URL=https://lumo22.onrender.com` (or your custom domain later). Update Stripe webhook to `https://lumo22.onrender.com/webhooks/stripe` (or `https://lumo22.com/webhooks/stripe` if you add a custom domain).

5. **Custom domain:** Render → your service → **Settings** → **Custom Domains** → add `lumo22.com`, then set `BASE_URL=https://lumo22.com` and the Stripe webhook URL to `https://lumo22.com/webhooks/stripe`.

6. Deploy and test as in Step 7.

---

## After deploy

- **Stripe:** Webhook endpoint URL must be your **live** `BASE_URL` + `/webhooks/stripe` (e.g. `https://lumo22.com/webhooks/stripe` or `https://yourapp.up.railway.app/webhooks/stripe`).
- **Test:** Use Stripe test mode and a test card; confirm intake email and delivery email with captions attachment.
