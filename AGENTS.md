# Agent / automation notes (Lumo 22)

**Git (required):** Use Git for version control and for deployment. When the user asks to commit, save, ship, or deploy: use `git add`, `git commit`, and `git push` as appropriate (unless they specify otherwise).

**Deploy:** Railway — usually **push to `main`** when the service is linked to GitHub. Manual upload: `railway up --no-gitignore` from the project root (see `docs/RAILWAY_DEPLOY.md`).

**Ignore** any stale instruction that this repo “does not use Git” — that is incorrect.

**Canonical Cursor rule:** `.cursor/rules/railway-deploy.mdc` (single source of truth for Git + Railway).
