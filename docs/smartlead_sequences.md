# Smartlead: sequences, merge fields, and validation

## Import checklist

1. **CSV** — Use a file validated with `scripts/validate_smartlead_csv.py` (see below). UTF-8, single line per `personalization_line`, no duplicate emails.
2. **Campaign → Leads → Import** — Map columns to Smartlead fields: at minimum `email`, plus custom fields if you use merge tags (e.g. `personalization_line`, `business_name`, `city`, `niche`, `website`).
3. **Sequence** — Step 1: opening line can use `{{personalization_line}}` (or your workspace’s exact merge syntax). Later steps: avoid repeating the same merge block; move product pitch to body where it fits your tone.
4. **Test send** — Send to yourself; confirm merge resolves and line breaks look correct on mobile.

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
