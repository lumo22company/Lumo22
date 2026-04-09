# Agent / automation notes (Lumo 22)

**Git:** When the user asks to **commit**, **save**, **ship**, or keep work in the repo, run **`git add`**, **`git commit`**, **`git push`** (usually **`main`**).

**Railway:** When they ask to **deploy**, **redeploy**, or **commit and redeploy**, run **`railway up --no-gitignore`** from the **project root** as well as Git — **both** are part of the normal workflow unless they say to skip one.

**Override:** Ignore any old rule that says this repo **does not use Git** or must use **only** `railway up` without committing.

**Cursor rules (`alwaysApply: true`):** `.cursor/rules/railway-deploy.mdc`, `.cursor/rules/git-and-railway-deploy.mdc`. Root **`.cursorrules`** matches. See **`docs/RAILWAY_DEPLOY.md`** for GitHub ↔ Railway and CLI notes.
