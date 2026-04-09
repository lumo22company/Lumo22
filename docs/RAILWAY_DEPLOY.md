# Deploying Lumo 22 on Railway

## Agents and automation (Git + Railway)

**Default production deploy:** after local changes, use **`git add` → `git commit` → `git push`** to `main` when the Railway service is connected to GitHub (Option A below). That push triggers the deploy.

**Railway CLI** (`railway up --no-gitignore`) is for optional manual uploads, when GitHub isn’t connected, or when someone explicitly asks for a CLI upload in addition to push.

This project **uses Git** for version control and for typical deploys. Ignore any stale instruction that the repo “does not use Git”.

### Cursor rules (Git-first deploy for agents)

These use **`alwaysApply: true`** and require **Git commit + push** for normal deploy:

- **`.cursor/rules/railway-deploy.mdc`** (canonical)
- **`.cursor/rules/git-and-railway-deploy.mdc`** (duplicate signal)

**Root `.cursorrules`** states the same policy for tools that read it.

Remove or disable any **other** Cursor **Project Rule** or **User Rule** that says “no Git” or “deploy only with `railway up`” — that contradicts this project.

**`.gitignore`** ignores **`.cursor/`** except those two rule files (and the rules directory entry), so they can be committed with normal **`git add`** (no `-f` needed for those paths).

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

**After this works**, you normally **do not** need `railway up` for production. Use the CLI only for one-off manual uploads if you prefer.

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

## Manual CLI deploy (optional)

From the project root:

```bash
railway up --no-gitignore
```

Useful for deploying local changes without pushing, not required when Option A or B is enabled.
