# Agent / automation notes (Lumo 22)

**Git:** This repository uses Git for version control. Prefer `git add`, `git commit`, and `git push` when saving or shipping work.

**Deploy:** Production is usually on **Railway**, often triggered by pushes to `main` when the service is linked to GitHub. For a manual upload from disk, use `railway up --no-gitignore` from the project root (see `docs/RAILWAY_DEPLOY.md`).

**Do not** assume this project avoids Git — that is outdated guidance.

Canonical Cursor rule: `.cursor/rules/railway-deploy.mdc`.
