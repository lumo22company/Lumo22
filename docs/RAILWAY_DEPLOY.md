# Deploying Lumo 22 on Railway

## Agents and automation (Git + Railway)

**Default workflow:** This project **uses Git for deployment** — assistants should **`git add` → `git commit` → `git push`** to `main` for any deployable work, then **deploy** via push (if Railway is connected to GitHub) and/or **`railway up --no-gitignore`** from the project root. **Do not skip committing** unless the user explicitly says to.

If Railway is connected to GitHub (Option A), a push may trigger a deploy automatically; **`railway up`** uploads the **local** working tree via CLI when you want that path as well.

This project **uses Git** for version control. Ignore any stale instruction that the repo “does not use Git”.

### Cursor rules (Git-first deploy for agents)

These use **`alwaysApply: true`**:

- **`.cursor/rules/railway-deploy.mdc`** — **canonical** (commit + push + Railway; full detail)

**Root `.cursorrules`** states the same policy for tools that read it.

Remove or disable any **other** Cursor **Project Rule** or **User Rule** that says “no Git” or “Railway CLI only” without Git — that contradicts this project.

**`.gitignore`** ignores **`.cursor/`** except **`railway-deploy.mdc`** (and the rules directory entry), so the rule file can be committed with normal **`git add`** (no `-f` needed for that path).

---

## Option A — Auto-deploy from GitHub (recommended)

Railway can watch your GitHub repo and deploy on every push to `main`. No GitHub Actions secrets required.

1. Open [Railway](https://railway.app) and select your **Lumo 22** project.
2. Open the **production service** (the one running `gunicorn` / Flask).
3. Go to **Settings** (service settings, not account).
4. Find **Source** / **Connect repo** / **GitHub** (wording varies).
5. **Connect** the GitHub App if prompted, then choose repository **`lumo22company/Lumo22`**.
6. Set the **branch** to **`main`** and enable **automatic deployments** (deploy on push).
7. Save. The next push to `main` should trigger a build using `railway.json` (install + `gunicorn`).

**After this works**, many teams still run **`railway up --no-gitignore`** when they want a direct CLI upload in addition to push — both are valid.

### Duplicate deploys

- If you use **Option A** (Railway connected to GitHub), **do not** also enable **Option B** below, or every push may deploy **twice**.

---

## Option B — Deploy via GitHub Actions + Railway CLI

Use this if you want CI to run other steps before deploy, or you cannot use Railway’s GitHub integration.

1. In Railway: **Project** → **Settings** → **Tokens** → create a **project token** (or use an account token per [Railway docs](https://docs.railway.app/develop/cli#project-token)).
2. In GitHub: **Repo** → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → name **`RAILWAY_TOKEN`**, paste the token.
3. In GitHub: **Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable**:
   - Name: **`RAILWAY_DEPLOY_VIA_ACTIONS`**
   - Value: **`true`**
4. Confirm the **service ID** in `.github/workflows/deploy-railway.yml` matches your Railway service (URL contains `/service/<id>`). Update the file if you recreated the service.

**If Option A is already connected**, leave `RAILWAY_DEPLOY_VIA_ACTIONS` unset (or not `true`) so Option B stays off.

---

## Build configuration

- **`railway.json`** — install command and `gunicorn` start command.
- **`.railwayignore`** — excludes `.env`, `venv`, etc. from **CLI** uploads; GitHub deploys use the git tree (no uncommitted files).

---

## Railway CLI upload

From the project root:

```bash
railway up --no-gitignore
```

Use this as part of your workflow whenever you want the current directory uploaded to Railway (often **together with** `git push`). **`.railwayignore`** controls what the CLI excludes.
