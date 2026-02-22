# Deploy LUMO22 so lumo22.com (or your live URL) works

Your app runs on **port 5001** locally. To have it live at **lumo22.com** (or a host URL), deploy this repo to a host and set your env vars there.

**No GitHub?** Use **Option C** below — deploy from your Mac with the Railway CLI (no GitHub needed).

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

## Option C: Deploy without GitHub (Railway CLI)

Use this if you can’t use GitHub right now. You deploy from your Mac; Railway hosts the app.

1. **Sign up at Railway:** Go to [railway.app](https://railway.app). Sign up with **email** (or Google) — you don’t need GitHub.

2. **Install the Railway CLI** (on your Mac, in Terminal):
   ```bash
   brew install railway
   ```
   If you don’t have Homebrew: [brew.sh](https://brew.sh) or download the CLI from [railway.app](https://railway.app).

3. **Log in and deploy from your project folder:**
   ```bash
   cd /Users/sophieoverment/LUMO22
   railway login
   ```
   A browser window opens; log in to Railway. Then:
   ```bash
   railway init
   ```
   Choose **Create new project** and a new **empty** service. Then:
   ```bash
   railway up
   ```
   Railway uploads your folder and builds the app. Wait until it finishes.

4. **Add env vars:** In the [Railway dashboard](https://railway.app/dashboard), open your project → your service → **Variables**. Add every variable from your `.env` (copy from your machine). Include at least: `FLASK_ENV=production`, `SECRET_KEY`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL`, `CAPTIONS_PAYMENT_LINK`, `STRIPE_WEBHOOK_SECRET`, and `BASE_URL` (see step 5).

5. **Get your live URL:** In Railway → your service → **Settings** → **Networking** → **Generate domain**. You’ll get a URL like `https://lumo22-production.up.railway.app`. Add it as a variable: `BASE_URL=https://that-full-url` (no trailing slash). Redeploy if needed (e.g. **Deploy** → **Redeploy**).

6. **Stripe webhook:** In Stripe → your webhook destination → edit the endpoint URL to your Railway URL + `/webhooks/stripe`, e.g. `https://lumo22-production.up.railway.app/webhooks/stripe`.

7. Test: open `BASE_URL/captions`, do a test payment, check the intake email and delivery email.

When you have GitHub later, you can connect the same Railway project to a repo and deploy from there instead.

---

## After deploy

- **Stripe:** Webhook endpoint URL must be your **live** `BASE_URL` + `/webhooks/stripe` (e.g. `https://lumo22.com/webhooks/stripe` or `https://yourapp.up.railway.app/webhooks/stripe`).
- **Test:** Use Stripe test mode and a test card; confirm intake email and delivery email with captions attachment.
