# See your changes after redeploy (no Git)

Your landing page uses **only** `static/css/landing.css` and the scripts in `static/js/`. The app serves `templates/landing.html` at `/`.

**Redeploys not updating?** Use **`railway up`** from your project folder in Terminal (not the dashboard “Redeploy” button). Dashboard redeploys build from GitHub; if you haven’t pushed, old code goes live. After `railway up`, wait for the build to finish, then hard refresh (Cmd+Shift+R). Open `/debug-deploy` on your live URL to confirm the new `asset_version` is running.

## Why “nothing changes” after redeploy (most likely)

**Railway is probably building from a Git repo (e.g. GitHub).** When you click “Redeploy” in the dashboard, it rebuilds from the **last commit in that repo**. The code you edit in Cursor is on your machine only—if you don’t push to that repo, redeploy keeps serving the same old code. So your updates never go live.

**Fix: Deploy the folder you’re actually editing** using the Railway CLI so the current files (including `templates/`, `static/`, `app.py`) are what get deployed.

---

## Deploy your current project folder (so changes show up)

1. **Install Railway CLI** (if needed): https://docs.railway.app/develop/cli  
   - Mac: `brew install railway`  
   - Or: `npm i -g @railway/cli`

2. **In Terminal, go to your project folder** (the one that contains `app.py`, `templates/`, `static/`):
   ```bash
   cd /Users/sophieoverment/LUMO22
   ```

3. **Log in and link the project** (one-time):
   ```bash
   railway login
   railway link
   ```
   When prompted, pick the project/environment that runs this site.

4. **Deploy the current folder** (this uploads the code you have now):
   ```bash
   railway up
   ```
   Wait for the deploy to finish.

5. **Check that the deploy used new code**  
   - Open your live site and do **View Page Source** (e.g. right‑click → View Page Source).  
   - Near the top of the `<body>` you should see a comment like:
     `<!-- deploy fingerprint: v=1736... -->`  
   - The value after `v=` includes a timestamp and the CSS file’s mtime. After `railway up`, this value should **change** if the new code is really running.  
   - Or open **`https://your-site.up.railway.app/debug-deploy`** — it returns JSON with `asset_version` and `landing_css_first_line` so you can confirm the running app has your latest CSS.

6. **Hard refresh** the page (e.g. **Cmd+Shift+R** on Mac) so the browser doesn’t use cached CSS/JS.

**If nothing changes after redeploy:**  
- Use **`railway up`** from the project folder (Terminal), not the “Redeploy” button in the Railway dashboard. The dashboard often rebuilds from GitHub; if you haven’t pushed, the old code is what gets deployed.  
- After `railway up`, wait for the build to finish, then hard refresh and check View Source for the new fingerprint.

---

## If you prefer to keep using the dashboard “Redeploy” button

Then the code Railway builds **must** come from the place your project is connected to (e.g. GitHub). So you’d need to get your local files into that repo (e.g. commit and push from the repo clone). Since you’re not using Git, the simplest way to see your changes is to use **Railway CLI** and `railway up` from the folder you edit (steps above).

---

## What’s already in place

- **Landing uses only `landing.css`** (no `style.css`), so your styles aren’t overridden.
- **Cache-busting** adds `?v=...` to CSS/JS so updated files load after a deploy.
- **`/debug-deploy`** on your live site returns JSON with the app’s `asset_version` and whether `landing.css` is present—useful to confirm what the running app has.
