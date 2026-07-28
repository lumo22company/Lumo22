# Smartlead: sequences, merge fields, and validation

## Import checklist

1. **CSV** — Use a file validated with `scripts/validate_smartlead_csv.py` (see below). UTF-8, single line per `personalization_line`, no duplicate emails.
2. **Campaign → Leads → Import** — Map columns to Smartlead fields: at minimum `email`, plus custom fields if you use merge tags (e.g. `personalization_line`, `business_name`, `city`, `niche`, `website`).
3. **Sequence** — Step 1: opening line can use `{{personalization_line}}` (or your workspace’s exact merge syntax). Later steps: avoid repeating the same merge block; move product pitch to body where it fits your tone.
4. **Test send** — Send to yourself; confirm merge resolves and line breaks look correct on mobile.
5. **Keep the UTMs** — Every link below carries `utm_campaign` (which sequence) and `utm_content` (`e1`/`e2`/`e3` — which email in the sequence). Without these, a click in Smartlead can't be matched to a landing-page visit or a sample order, and a campaign that produces no customers is impossible to diagnose. If you add a new sequence, tag its links the same way.

## Email sequence — free 3-caption sample offer (current default for cold outreach)

Lead with the free sample (`https://www.lumo22.com/captions-sample`): lowest-friction CTA, no card,
delivered by email after a ~2-minute form. The full 30-day pack is a secondary mention. Use this for
new cold campaigns. Merge fields: `{{company_name}}`, `{{personalization_line}}`, `%signature%`.

Email 1 subject:

```text
3 free captions for {{company_name}}?
```

Email 1 body:

```text
Hi,

{{personalization_line}}

Quick one — can I send you 3 free social captions written in your voice? Fill out a short form (about 2 minutes) and they land in your inbox. No card, no catch — just so you can see how we write before deciding anything.

Here's the link: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=sample3&utm_content=e1

If you like them, there's a full 30-day pack (one-off or monthly), but the 3 are yours either way.

Sophie

%signature%
```

Email 2 subject:

```text
Re: 3 free captions for {{company_name}}?
```

Email 2 body:

```text
Hi,

Following up in case my last note got buried.

The bit that usually slips for businesses like yours isn't the work itself — it's keeping content consistent around services, offers and the questions clients keep asking.

If you want to see how we'd write that in your voice, the 3 free captions are still here (2-min form, no card): https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=sample3&utm_content=e2

Sophie

%signature%
```

Email 3 subject:

```text
Last note from me
```

Email 3 body:

```text
Hi,

Won't clutter your inbox further — last note from me.

If 3 free captions in {{company_name}}'s voice would be useful, the form's here: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=sample3&utm_content=e3

If not, reply "stop" and I'll close the loop.

Sophie

%signature%
```

## Dedupe and junk email

```bash
python scripts/dedupe_smartlead_csv.py exports/your.csv --out exports/your_deduped.csv
python scripts/dedupe_smartlead_csv.py exports/your.csv --out exports/your_deduped.csv --drop-wix-sentry
```

## Personalization generation (repo scripts)

| Goal | Command sketch |
|------|------------------|
| Fitness + Apify Maps categories | `python scripts/enrich_personalization_fitness_from_apify.py LEADS.csv --apify-csv MAPS.csv --out OUT.csv` |
| Rule-only, no Apify (uses `niche` column) | Same command **without** `--apify-csv` |
| AI lines (Claude/OpenAI per `.env`) | Add `--use-ai` and optional `--vertical auto\|fitness\|general` |
| Dry run | `--use-ai --dry-run --limit 3` |

After AI or rule refresh, **re-run validation** on the output CSV before import.

## Validation

```bash
python scripts/validate_smartlead_csv.py exports/your_file.csv
python scripts/validate_smartlead_csv.py exports/your_file.csv --json-out exports/validation_report.json
```

**Errors (exit 1):** missing `email` / `personalization_line`, empty values, invalid-looking email, duplicate emails, newlines inside `personalization_line`.

**Warnings:** very short/long lines, template “monoculture” (same sentence shape for most rows), business name or city missing from the line, product words in the opener (`Lumo`, “we handle… captions”), smart quotes in text.

Use `--warn-only` only if you intentionally want exit 0 despite errors (not recommended for go-live).

## Multi-niche automation (one command)

You can run your whole scrape -> dedupe -> personalization -> validation flow for multiple niches via:

```bash
python scripts/run_niche_pipeline.py --config configs/niches.json
```

### Smartlead auto-import (optional)

Set API key in `.env`:

```env
SMARTLEAD_API_KEY=your_smartlead_api_key
```

Dry run import (no API writes):

```bash
python scripts/run_niche_pipeline.py --config configs/niches.json --import-smartlead --dry-run-import
```

Real import:

```bash
python scripts/run_niche_pipeline.py --config configs/niches.json --import-smartlead
```

The script imports `smartlead_new_only_<slug>_<date>.csv` rows into each niche's
`smartlead_campaign_id` using Smartlead API batches (default 50 rows).

If API keys are unavailable on your plan, run without `--import-smartlead`.
The script prints a "Manual Upload Checklist" with campaign ID + exact CSV path.

### One-time setup

1. Copy `configs/niches.example.json` -> `configs/niches.json`.
2. Fill each niche:
   - `slug` (short machine name),
   - `apify_task_id` (Apify actor task to run),
   - `smartlead_campaign_id` (for routing/tracking).
3. Set `APIFY_TOKEN` in your environment or `.env`.

### What it produces

For each enabled niche + date:

- `exports/apify_raw_<slug>_<date>.csv`
- `exports/apify_deduped_<slug>_<date>.csv`
- `exports/smartlead_ready_<slug>_<date>.csv`
- `exports/smartlead_new_only_<slug>_<date>.csv` (import this one)
- `exports/validation_<slug>_<date>.json`

Plus one run summary:

- `exports/pipeline_summary_<date>.json`
- `exports/seen_leads_registry.csv` (persistent do-not-reimport registry)

### Incremental mode (no duplicate reprocessing)

`run_niche_pipeline.py` now automatically excludes leads that already appeared in:

- previous `smartlead_ready_*.csv`,
- previous `smartlead_super_safe_*.csv`,
- previous `SMARTLEAD_IMPORT_*.csv`,
- `exports/seen_leads_registry.csv`.

It writes only net-new leads to `smartlead_new_only_<slug>_<date>.csv` and appends
their dedupe keys to `seen_leads_registry.csv`.

This means you should import `smartlead_new_only_*.csv` going forward.

### Useful flags

```bash
# Use existing raw CSV files, skip Apify API calls
python scripts/run_niche_pipeline.py --skip-apify

# Process only first enabled niche while testing
python scripts/run_niche_pipeline.py --limit-niches 1

# Override date suffix
python scripts/run_niche_pipeline.py --date 2026-05-06
```

### Scheduling (example cron)

```bash
0 6 * * * cd /Users/sophieoverment/LUMO22 && /usr/bin/python3 scripts/run_niche_pipeline.py --config configs/niches.json >> logs/niche_pipeline.log 2>&1
```

Or install it automatically:

```bash
./scripts/setup_daily_pipeline_cron.sh
```

Optional custom time (example 07:30 daily):

```bash
./scripts/setup_daily_pipeline_cron.sh "30 7 * * *"
```

## Aesthetic clinics UK campaign

### Current status

`configs/niches.json` includes disabled placeholders for:

- `aesthetic_clinics_bristol`
- `aesthetic_clinics_bath`

They are intentionally disabled until you create matching Apify tasks and Smartlead campaigns. This prevents the daily pipeline from scraping/importing a new niche before the campaign copy, schedule, and mailbox capacity are ready.

### Apify task setup

Use the Google Maps Scraper actor and create one saved task per city.

Suggested search terms:

```text
aesthetic clinic
skin clinic
laser clinic
beauty clinic
medical spa
facial clinic
botox clinic
dermal filler clinic
laser hair removal
```

Suggested locations:

```text
Bristol, UK
Bath, UK
```

Suggested starting limit:

```text
25 places per search term
```

After saving each Apify task, paste the task ID into the matching disabled entry in `configs/niches.json`, then change `enabled` to `true` only when the Smartlead campaign is ready.

### Smartlead setup

Create one campaign per city or one combined "Aesthetic Clinics UK" campaign. If using the same mailbox as fitness, keep the campaign daily cap conservative so follow-ups and fitness sends do not starve each other.

Recommended starting settings:

- Daily campaign cap: 8-10 new leads per day
- Schedule: Europe/London, weekdays, 09:00-17:00
- Send priority: balanced new leads / follow-ups, not 100% new leads
- Footer: include your business postal address before launching

### Copy-paste sequence

> Recommended: use the **free 3-caption sample sequence** above for cold outreach (higher reply rate, no card). The full-pack sequence below is kept for reference / warm follow-ups.

Email 1 subject:

```text
30 Days of Social Media Captions for {{company_name}}
```

Email 1 body:

```text
Hi,

{{personalization_line}}

Quick one — would 30 days of social captions, drafted in your voice from a 3-minute form, actually be useful? Or have you got that sorted?

If useful: https://www.lumo22.com/captions?utm_source=smartlead&utm_medium=email&utm_campaign=aesthetics_uk&utm_content=e1

There's a one-off option if you just want to test it — no subscription needed.

Sophie

%signature%
```

Email 2 subject:

```text
Re: 30 Days of Social Media Captions for {{company_name}}
```

Email 2 body:

```text
Hi,

Following up in case the first note got buried.

For aesthetic and beauty clinics I speak to, the bit that usually slips isn't the treatments — it's keeping content consistent around services, availability, client questions and offers.

If that sounds familiar: https://www.lumo22.com/captions?utm_source=smartlead&utm_medium=email&utm_campaign=aesthetics_uk&utm_content=e2 (3-min form, captions in your voice back in 15 mins)

Sophie

%signature%
```

Email 3 subject:

```text
Last note from me
```

Email 3 body:

```text
Hi,

Won't clutter your inbox further — this is my last note.

If 30 days of social captions in your clinic's voice would make next month easier, the form's here: https://www.lumo22.com/captions?utm_source=smartlead&utm_medium=email&utm_campaign=aesthetics_uk&utm_content=e3

If not, reply "stop" and I'll close the loop.

Sophie

%signature%
```

### Run command once IDs are added

```bash
python scripts/run_niche_pipeline.py --config configs/niches.json --only-slug aesthetic_clinics_bristol --probe-delay 0.2 --probe-timeout 6
```

Then import:

```text
exports/smartlead_new_only_aesthetic_clinics_bristol_<date>.csv
```

## Job intent — companies hiring social media roles

Use when leads come from job boards (Reed, Indeed, LinkedIn Jobs) via `scripts/scrape_job_intent.py`.
These companies have **active hiring intent** for social/content help — position Lumo 22 as a faster,
cheaper bridge before they commit to a full hire.

### Smartlead field mapping

| CSV column | Smartlead field |
|------------|-----------------|
| `email` | Email |
| `business_name` | `{{company_name}}` |
| `job_title` | Custom field → `{{job_title}}` |
| `personalization_line` | Custom field → `{{personalization_line}}` |
| `job_url` | Custom field (optional, for your notes) |

Create a **separate campaign** from clinic/fitness outreach. Recommended mailbox: Sophie (UK Reed leads)
or Mabel (US leads when you add them). Keep daily cap low (5–8/day) while testing.

### Free enrichment (no Apify)

Job boards rarely include emails. Use this two-step stack:

```bash
# 1) Resolve company websites (DuckDuckGo + domain verify — free)
python scripts/find_company_websites.py exports/smartlead_ready_jobs_smm_intent_<date>.csv \\
  --out exports/jobs_with_websites_<date>.csv --skip-recruiters --delay 1.0

# 2) Probe home + /contact pages for public emails (free, stdlib + requests)
python scripts/enrich_csv_emails_from_websites.py exports/jobs_with_websites_<date>.csv \\
  --out exports/jobs_with_emails_<date>.csv --delay 0.35 --timeout 6
```

Filter to rows with email before Smartlead import. Expect **30–60%** email yield on UK employer
names (lower if many recruitment-agency postings — use `--skip-recruiters`).

Re-run weekly; job posts go stale in 2–4 weeks.

### Copy-paste sequence — hiring intent (free 3-caption sample)

Email 1 subject:

```text
Before you hire for {{job_title}}?
```

Email 1 body:

```text
Hi,

{{personalization_line}}

Quick thought — a lot of teams post for a {{job_title}} when what they really need first is consistent content: captions, Story prompts, and a month mapped out in their voice.

Would 3 free captions be worth a look before you commit to a hire? Two-minute form, no card, delivered by email: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_intent&utm_content=e1

If they land well, there's a full 30-day pack — but the 3 are yours either way.

Sophie

%signature%
```

Email 2 subject:

```text
Re: {{job_title}} at {{company_name}}
```

Email 2 body:

```text
Hi,

Following up in case my last note got buried.

Hiring takes weeks. Posting doesn't wait — and the gap is usually content, not strategy.

If you want to see how we'd write for {{company_name}} before the role is filled: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_intent&utm_content=e2 (3 captions, your voice, no card).

Sophie

%signature%
```

Email 3 subject:

```text
Last note from me
```

Email 3 body:

```text
Hi,

Last note from me — won't follow up again.

If 3 free captions would help while you're hiring for {{job_title}}, the form's here: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_intent&utm_content=e3

If not, reply "stop" and I'll close the loop.

Sophie

%signature%
```

### Notes for recruitment-agency job posts

Some Reed/Indeed listings are posted by agencies (e.g. "Stripe Recruitment") rather than the end employer.
Either skip them (`find_company_websites.py --skip-recruiters`) or use softer copy — don't assume
the reader is the hiring manager at the business in the job title.

---

## Job intent — Smartlead campaign setup (step by step, no import yet)

Build the campaign **empty** first. Import leads only when copy and settings look right.

### Step 1 — Create the campaign

1. Smartlead → **Email Campaigns** → **+ Create Campaign**
2. **Name:** `UK Hiring SMM — Job intent`
3. Leave **Draft** / **Paused** — do not start until test send passes

### Step 2 — Connect mailbox

1. Attach **sophie@lumo22.com** only (UK Reed leads; Mabel is for US)
2. Confirm Sophie’s **signature** (name, lumo22.com, UK postal address in footer)

### Step 3 — Custom fields (create before import)

| Smartlead custom field | CSV column |
|------------------------|------------|
| `job_title` | `job_title` |
| `personalization_line` | `personalization_line` |
| `job_url` | `job_url` (optional) |

`business_name` → `{{company_name}}` on import.

### Step 4 — Schedule (UK)

| Setting | Value |
|---------|--------|
| Timezone | `Europe/London` |
| Days | Mon–Fri |
| Hours | 09:30–16:30 |
| Max new leads/day | **5** (raise to 8 after 1 week) |
| Min gap between sends | 3–5 min |

### Step 5 — Sequence delays

| Step | When |
|------|------|
| Email 1 | Day 0 |
| Email 2 | **+3 days** |
| Email 3 | **+5 days** after Email 2 |

### Step 6 — Sequence v2 (high conversion) — use this

Merge fields: `{{company_name}}`, `{{job_title}}`, `{{personalization_line}}`, `%signature%`.

**Why this converts:** hiring signal opener → one CTA (free sample) → time/cost reframe → clean breakup.

#### Email 1 subject

```text
{{company_name}} — before the {{job_title}} hire?
```

#### Email 1 body

```text
Hi,

{{personalization_line}}

Most teams I speak to post for a {{job_title}} when the real bottleneck is content — captions and Stories that sound like them, every week, without another person to manage.

If that’s you, I can send 3 free captions in {{company_name}}’s voice. Two-minute form, no card, in your inbox: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_v2&utm_content=e1

Worth a look before you shortlist candidates?

Sophie

%signature%
```

#### Email 2 subject

```text
Re: {{company_name}} {{job_title}}
```

#### Email 2 body

```text
Hi,

Quick follow-up — hiring usually takes 4–8 weeks. Posting can’t pause that long.

A lot of businesses bridge the gap with done-for-you captions (30 days mapped out, your tone) while the role is still open — cheaper than a hire, faster than agency.

If you want to see the quality first: 3 free captions, same form, no catch: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_v2&utm_content=e2

Sophie

%signature%
```

#### Email 3 subject

```text
Close the loop?
```

#### Email 3 body

```text
Hi,

Last note from me on this.

If 3 free captions for {{company_name}} would help while you’re filling the {{job_title}} role: https://www.lumo22.com/captions-sample?utm_source=smartlead&utm_medium=email&utm_campaign=hiring_v2&utm_content=e3

If not useful, reply “stop” and I won’t follow up again.

Sophie

%signature%
```

### Step 7 — Test send (no bulk import)

1. **Send test email** on Email 1 → your own inbox
2. Check merge fields, link, signature on mobile
3. Fix before importing any leads

### Step 8 — When you import later

File: `exports/smartlead_new_only_jobs_smm_intent_<date>.csv` (23 leads as of 2026-06-18).

Before import: remove recruitment agencies and bad website matches. Start with daily cap **5**.

### Step 9 — Go live

Import CSV → map fields → **Start** campaign. Pause if bounce rate > 5% in first 48h.

