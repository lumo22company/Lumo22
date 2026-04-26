# Agent / automation notes (Lumo 22)

**Git — always commit:** Use **`git add`** → **`git commit`** → **`git push`** (usually **`main`**) for work the user expects in the repo or production. When they ask to **commit**, **deploy**, **redeploy**, or **ship**, **always commit** (do not deploy only via Railway CLI unless they say to skip Git).

**Railway:** **`railway up --no-gitignore`** from the **project root** for CLI upload / redeploy; use **with** Git commit + push unless they want CLI-only.

**Cursor** (`alwaysApply: true`): **`.cursor/rules/railway-deploy.mdc`** (canonical). See **`docs/RAILWAY_DEPLOY.md`** for GitHub ↔ Railway and CLI notes.

## Security roadmap (quick ref)

- **Beginner walkthrough (checkboxes):** `docs/SECURITY_PRIVACY_WALKTHROUGH.md`
- **Dependency audit:** CI job `dependency-audit` in `.github/workflows/tests.yml` (`pip-audit -r requirements.txt`).
- **ZAP baseline:** run manually — GitHub **Actions → Security — ZAP baseline (manual)** — enter staging `target_url`. See `SECURITY_PRIVACY_REVIEW.md`.

## Captions reminder / email dedupe (Supabase SQL)

After pulling changes that mention duplicate emails or reminder jobs, confirm these have been run in the **Supabase SQL editor** for production (order matters only where noted):

1. **`database_caption_orders_checkout_email_dedupe.sql`** — `checkout_confirmation_email_sent_at` (order confirmation + form link dedupe across webhook/API).
2. **`database_caption_reminder.sql`** — `reminder_sent_period_end`, `reminder_opt_out` (pre-pack subscription reminders).
3. **`database_caption_orders_intake_early_reminder_sent_at.sql`** — subscription ~2h form nudge dedupe.
4. **`database_caption_orders_one_off_intake_reminder_sent_at.sql`** — one-off 24–48h form reminder dedupe.
5. **`database_caption_orders_upgrade_reminder.sql`** — one-off upgrade reminder (`upgrade_reminder_sent_at` / opt-out).
6. **`database_caption_orders_claim_pre_pack_reminder.sql`** — RPC `claim_pre_pack_reminder` (atomic pre-pack reminder when cron and in-app scheduler overlap).
7. **`database_caption_orders_plan_change_confirmation_dedupe.sql`** — `plan_change_confirmation_*` + RPC `claim_plan_change_confirmation` (atomic plan-change confirmation when Stripe webhooks and billing API overlap).

If a migration is missing, logs usually mention the column or function name; run the matching file and redeploy.
