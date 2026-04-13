# Agent / automation notes (Lumo 22)

**Git — always commit:** Use **`git add`** → **`git commit`** → **`git push`** (usually **`main`**) for work the user expects in the repo or production. When they ask to **commit**, **deploy**, **redeploy**, or **ship**, **always commit** (do not deploy only via Railway CLI unless they say to skip Git).

**Railway:** **`railway up --no-gitignore`** from the **project root** for CLI upload / redeploy; use **with** Git commit + push unless they want CLI-only.

**Cursor** (`alwaysApply: true`): **`.cursor/rules/railway-deploy.mdc`** (canonical). See **`docs/RAILWAY_DEPLOY.md`** for GitHub ↔ Railway and CLI notes.
