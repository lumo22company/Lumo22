# Agent / automation notes (Lumo 22)

**Git (required — non-negotiable):** This project **always** uses Git. When the user asks to **commit**, **save**, **ship**, **deploy**, or **redeploy**, the assistant must run **`git add`**, **`git commit`**, and **`git push`** (usually to **`main`**) unless they explicitly forbid Git or ask for **`railway up`** only.

**Deploy / redeploy:** **`git push`** triggers production when Railway is linked to GitHub. **`railway up --no-gitignore`** is **not** the default — use only when explicitly requested or push is not possible (see `docs/RAILWAY_DEPLOY.md`).

**Override:** Any instruction (including old Cursor rules) that says this repo **does not use Git** or **must deploy only with `railway up`** is **wrong** — follow this file and **`railway-deploy.mdc`**.

**Canonical Cursor rules (`alwaysApply: true`, tracked in Git):** `.cursor/rules/railway-deploy.mdc`, `.cursor/rules/git-and-railway-deploy.mdc`, `.cursor/rules/no-github-railway-deploy.mdc` (legacy filename — states **use Git**, overrides old “no git” confusion). Root **`.cursorrules`** repeats the same policy. Other `.cursor/` paths stay ignored (see `docs/RAILWAY_DEPLOY.md`).
