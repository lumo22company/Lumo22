# Agent / automation notes (Lumo 22)

**Git for deployment:** Always **`git add`** → **`git commit`** → **`git push`** (usually **`main`**) when completing work the user expects in production, or when they ask to **commit**, **deploy**, **redeploy**, or **ship**. Do not leave changes uncommitted unless they explicitly say to skip.

**Railway:** **`railway up --no-gitignore`** from the **project root** when they want a CLI upload / redeploy, **together with** Git push unless they only want one path.

**Cursor** (`alwaysApply: true`): **`.cursor/rules/railway-deploy.mdc`** (canonical). See **`docs/RAILWAY_DEPLOY.md`** for GitHub ↔ Railway and CLI notes.
