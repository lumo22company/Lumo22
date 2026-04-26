# Security & privacy — step-by-step (beginner-friendly)

You do **not** need to understand attack types. Follow the steps in order; check boxes as you go. Detailed env vars are in **`PRODUCTION_ENV_SETUP.md`**. Technical risks and code notes are in **`SECURITY_PRIVACY_REVIEW.md`**.

---

## Words you’ll see (plain English)

| Term | Meaning |
|------|--------|
| **Secret / API key** | A password machines use to talk to Stripe, SendGrid, etc. Never put it in git or public chat. |
| **Environment variables** | Settings stored in Railway (or similar), not in your code. |
| **Webhook** | Stripe (or others) calling *your* server when something happens; must be verified so fakes are rejected. |
| **RLS (Row Level Security)** | Supabase rules: “this user can only see *their* rows.” |
| **CI / GitHub Actions** | Automatic checks when you push code (tests + dependency audit). |

---

## Part 1 — GitHub (about 10 minutes)

**Goal:** Your code changes are checked automatically.

1. [ ] Open your repo on GitHub → **Actions**.
2. [ ] Click the latest **Tests** run on `main`. It should be **green** (passed). That run includes **pytest** (logic tests) and **pip-audit** (known vulnerable dependencies).
3. [ ] If anything is **red**, open the failed job and read the error (often a missing test fix or a dependency that needs upgrading).
4. [ ] If **Dependabot** opened pull requests (“Bump xyz”), read each one. For patch/minor updates, merging after a green CI is usually fine. If unsure, ask someone or merge one at a time and redeploy.

---

## Part 2 — Railway (or your host) (about 20–30 minutes)

**Goal:** Production has real secrets, debug is off, URLs are correct.

1. [ ] Open **Railway** → your Lumo app → **Variables** (same idea on other hosts: “Environment”).
2. [ ] Confirm **`FLASK_ENV`** = `production` and **`FLASK_DEBUG`** = `False` (so visitors don’t see developer error pages with stack traces).
3. [ ] Confirm **`SECRET_KEY`** is a **long random** value — **not** the default `dev-secret-key-change-in-production`. Generate on your Mac: Terminal → `openssl rand -hex 32` → paste the result into Railway as `SECRET_KEY`.
4. [ ] Confirm **`BASE_URL`** is your real public site, **https**, **no** trailing slash (e.g. `https://www.lumo22.com`).
5. [ ] Work through **`PRODUCTION_ENV_SETUP.md`** sections 1–3 so every **required** variable exists (Supabase, Stripe, SendGrid, AI keys, caption price IDs, etc.). If the app starts in production, the strict checks already passed — but a human checklist still catches wrong *values* (e.g. test Stripe key on a live site).
6. [ ] **`CRON_SECRET`**: if you use scheduled reminder calls to your app, set this to another `openssl rand -hex 32` and use the same value in the cron job URL/header your scheduler sends. If you don’t use that cron, you can still set it for when you enable it later.
7. [ ] **`CAPTIONS_DELIVER_TEST_SECRET`**: only needed if you intentionally use the deliver-test URL in production. If you set it, the app requires `?secret=...`. If you never use that endpoint in prod, you can leave it unset; the app still blocks unsafe use when production rules apply.

**Rule:** Never paste live secrets into GitHub issues, screenshots, or TikTok. Use Railway’s masked UI or a password manager.

---

## Part 3 — Stripe (about 10 minutes)

**Goal:** Payments and webhooks are really yours, not a copy-paste from test mode.

1. [ ] **Stripe Dashboard** → **Developers** → **Webhooks** → your endpoint should be your **live** `https://…` URL.
2. [ ] The **signing secret** in Railway (`STRIPE_WEBHOOK_SECRET`) must match **that** webhook (live vs test are different).
3. [ ] API key in Railway should be **`sk_live_…`** for the live site (and **`sk_test_…`** only on a staging copy of the app).

---

## Part 4 — Supabase (about 15–30 minutes)

**Goal:** One customer cannot read another customer’s orders by guessing IDs.

1. [ ] Log into **Supabase** → your project.
2. [ ] Open **Authentication** / **Table editor** as needed, but the important part is **SQL** or **Database** → policies for tables that hold **customers** and **caption_orders** (and anything similar).
3. [ ] Confirm **RLS is enabled** and policies match how your app works (server often uses **service role** for some jobs; the **anon** key must never allow broad `SELECT` on other users’ rows from a browser).
4. [ ] If you’re unsure, Supabase docs on “Row Level Security” and your table names are the next read — or ask a developer for one focused “RLS review” session.

**Rule:** The **service role** key belongs **only** on the server (Railway). Never put it in front-end JavaScript or a mobile app.

---

## Part 5 — Email (SendGrid) (about 10 minutes)

**Goal:** Your emails are trusted and harder to spoof.

1. [ ] In **SendGrid**, confirm **domain authentication** (SPF/DKIM) for the domain you send from (e.g. `lumo22.com`).
2. [ ] **`FROM_EMAIL`** in Railway matches a verified sender.

---

## Part 6 — Privacy page vs reality (about 10 minutes)

**Goal:** What you say in public matches what the product does.

1. [ ] Open your live site → **Privacy** (`/privacy`).
2. [ ] Read **who you share data with** (Stripe, SendGrid, Supabase, AI providers). If you add a new big vendor later, update the page.
3. [ ] The template in the repo is **`templates/_privacy_content.html`** — that’s what to edit when you change the policy text.

---

## Part 7 — Internal security note (about 15 minutes)

**Goal:** You know what was already reviewed in code.

1. [ ] Open **`SECURITY_PRIVACY_REVIEW.md`** in the repo.
2. [ ] Read the **executive summary** table at the top (high/medium items).
3. [ ] Skim **recommended actions** at the bottom — items with strikethrough are already addressed in code; open items (e.g. reducing personal data in logs) are **improvements over time**, not “you failed if not done today.”

---

## Part 8 — Optional but strong (when you have a staging URL)

**Goal:** Catch misconfigurations before bad actors do.

1. [ ] GitHub → **Actions** → **Security — ZAP baseline (manual)** → **Run workflow** → paste **staging** `https://…` (not production the first time, unless you accept the risk).
2. [ ] Download the **artifact** report when the job finishes. High-severity items deserve a fix or a written “false positive” note.
3. [ ] **Load / stress:** only against **staging** or a dedicated test deployment (see earlier advice: k6, Loader.io, etc.). Increase traffic slowly.

---

## Part 9 — Habits (ongoing)

1. [ ] After a **big feature** (new payment flow, new table, new integration), skim **`SECURITY_PRIVACY_REVIEW.md`** again and ensure CI is still green.
2. [ ] **Merge Dependabot** security-style updates reasonably often.
3. [ ] If you sell to companies that ask for proof: budget a **professional penetration test** once; this checklist is **not** that certificate.

---

## Already automated in this repo (you don’t set these up)

- **Tests + dependency audit** on each push/PR to `main` (GitHub Actions).
- **Dependabot** config for pip + GitHub Actions (weekly PRs).
- **Manual ZAP** workflow for a URL you choose.

---

## If you’re stuck

- App won’t start in production → Railway **logs** often mention **`PRODUCTION_ENV_SETUP.md`** and the missing variable name.
- Green CI but something feels wrong on the live site → use **Part 8** on staging, or ask a developer to trace that specific URL.
