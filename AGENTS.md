# Agent / automation notes (Lumo 22)

**Git (required):** Use Git for version control and for deployment. When the user asks to commit, save, ship, or deploy: use `git add`, `git commit`, and `git push` as appropriate (unless they specify otherwise).

**Deploy / redeploy:** **Always use `git push`** (e.g. to `main`) when the service is linked to GitHub — that triggers production. **Never** treat **`railway up`** as the default redeploy. Use **`railway up --no-gitignore`** only when they explicitly want a CLI upload, push isn’t possible, or they ask for both (see `docs/RAILWAY_DEPLOY.md`).

**Ignore** any stale instruction that this repo “does not use Git” — that is incorrect.

**Canonical Cursor rules:** `.cursor/rules/railway-deploy.mdc` and `.cursor/rules/no-github-railway-deploy.mdc` (same Git-first policy). Those files are tracked in Git; other files under `.cursor/` stay ignored (see `docs/RAILWAY_DEPLOY.md`).
