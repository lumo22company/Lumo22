# See your changes after redeploy

Your landing page uses **only** `static/css/landing.css` and the scripts in `static/js/`. The app serves `templates/landing.html` at `/`.

## Recommended: Git + Railway (GitHub)

1. **Commit and push** your changes to the branch Railway builds from (usually **`main`**):
   ```bash
   git add -A
   git commit -m "Describe your change"
   git push
   ```
2. Railway (when connected to GitHub) will build and deploy from that push.
3. After the deploy finishes, **hard refresh** (Cmd+Shift+R). Open `/debug-deploy` on your live URL to confirm the new `asset_version` is running.

## If Railway still shows old code

**Dashboard “Redeploy”** often rebuilds from the **last commit GitHub has**. If you only edited locally and didn’t push, the live site won’t change until you **push** (or use the CLI upload below).

## Manual CLI upload (fallback)

Upload the **exact folder you’re editing** without relying on GitHub:

1. Install Railway CLI: https://docs.railway.app/develop/cli  
2. From the project root (contains `app.py`, `templates/`, `static/`):
   ```bash
   railway up --no-gitignore
   ```
3. Wait for the build, then hard refresh and check **`/debug-deploy`** or View Source for the deploy fingerprint.

Use this when GitHub isn’t connected, you need to ship uncommitted files, or you were told to deploy via CLI.

---

## Why “nothing changes” after redeploy (common causes)

- **GitHub deploy:** You didn’t **push** — Railway built an old commit.
- **Wrong deploy path:** Use **`railway up`** from the project folder you actually edit, not a stale clone elsewhere.

---

## What’s already in place

- **Landing uses only `landing.css`** (no `style.css`), so your styles aren’t overridden.
- **Cache-busting** adds `?v=...` to CSS/JS so updated files load after a deploy.
- **`/debug-deploy`** on your live site returns JSON with the app’s `asset_version` and whether `landing.css` is present—useful to confirm what the running app has.
