#!/usr/bin/env python3
"""
Validate Smartlead-style lead CSVs before import: emails, personalization_line quality, dupes.

Exits with code 1 if any ERROR-level issue is found (unless --warn-only).
Writes a short human report to stdout; optional --json-out for machine-readable summary.

Example:
  python scripts/validate_smartlead_csv.py exports/smartlead_super_safe_batch_100_merged_emails.csv
  python scripts/validate_smartlead_csv.py exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_personalized_ai.csv --json-out exports/validation_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def _norm(s: str) -> str:
    return (s or "").strip()


def _template_key(line: str, name: str, city: str) -> str:
    """Collapse obvious name/city slots so we can spot one template reused everywhere."""
    k = (line or "").strip()
    if name:
        k = re.sub(re.escape(name.strip()), "__NAME__", k, flags=re.IGNORECASE)
    if city:
        k = re.sub(re.escape(city.strip()), "__CITY__", k, flags=re.IGNORECASE)
    k = re.sub(r"\s+", " ", k)
    return k


def validate_rows(rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []

    if not rows:
        errors.append({"row": 0, "level": "error", "code": "empty_file", "message": "No data rows"})
        return errors, warnings

    fields = {k.lower() for k in rows[0].keys()}
    if "email" not in fields:
        errors.append({"row": 0, "level": "error", "code": "missing_column", "message": "Missing required column: email"})
    if "personalization_line" not in fields:
        errors.append(
            {"row": 0, "level": "error", "code": "missing_column", "message": "Missing required column: personalization_line"}
        )
    if errors:
        return errors, warnings

    # Normalise keys to lowercase for access
    norm_rows: list[dict[str, str]] = []
    for r in rows:
        norm_rows.append({(k or "").lower(): (v or "").strip() for k, v in r.items()})

    emails_seen: dict[str, int] = {}
    for idx, r in enumerate(norm_rows, start=2):
        email = _norm(r.get("email", ""))
        pl = r.get("personalization_line", "")
        name = _norm(r.get("business_name", ""))
        city = _norm(r.get("city", ""))

        if not email:
            errors.append({"row": idx, "level": "error", "code": "empty_email", "message": "email is empty"})
        elif not _EMAIL_RE.match(email):
            errors.append({"row": idx, "level": "error", "code": "bad_email", "message": f"email looks invalid: {email!r}"})
        else:
            key = email.casefold()
            if key in emails_seen:
                hint = ""
                if "sentry.wixpress.com" in email or "sentry-next.wixpress.com" in email:
                    hint = " (Wix/Sentry noise — drop or replace before import)"
                errors.append(
                    {
                        "row": idx,
                        "level": "error",
                        "code": "duplicate_email",
                        "message": f"duplicate email {email!r} (also row {emails_seen[key]}){hint}",
                    }
                )
            else:
                emails_seen[key] = idx

        if not (pl or "").strip():
            errors.append({"row": idx, "level": "error", "code": "empty_personalization", "message": "personalization_line is empty"})
        else:
            if "\n" in pl or "\r" in pl:
                errors.append(
                    {"row": idx, "level": "error", "code": "multiline_personalization", "message": "personalization_line must be single line (no newlines)"}
                )
            L = len(pl)
            if L < 35:
                warnings.append(
                    {"row": idx, "level": "warn", "code": "short_personalization", "message": f"personalization_line is only {L} chars (may feel thin)"}
                )
            if L > 340:
                warnings.append(
                    {"row": idx, "level": "warn", "code": "long_personalization", "message": f"personalization_line is {L} chars (check Smartlead field limits / mobile preview)"}
                )
            low = pl.lower()
            if "lumo" in low or "we handle the captions" in low or "we handle your captions" in low:
                warnings.append(
                    {
                        "row": idx,
                        "level": "warn",
                        "code": "product_in_opener",
                        "message": "Opener mentions product/vendor; consider keeping line 1 empathy-only if your template pitches in step 2",
                    }
                )
            if re.search(r"[\u2018\u2019\u201c\u201d\u2026]", pl):
                warnings.append(
                    {
                        "row": idx,
                        "level": "warn",
                        "code": "fancy_quotes",
                        "message": "Contains smart quotes or ellipsis; plain ASCII is safer for CSV/merge tools",
                    }
                )
            if name and name.lower() not in low:
                warnings.append(
                    {
                        "row": idx,
                        "level": "warn",
                        "code": "name_not_in_line",
                        "message": f"business_name {name!r} not found as substring in personalization (can be OK if shortened)",
                    }
                )
            if city and city.lower() not in low:
                warnings.append(
                    {
                        "row": idx,
                        "level": "warn",
                        "code": "city_not_in_line",
                        "message": f"city {city!r} not found in personalization (optional for your tone)",
                    }
                )

    # Template concentration (after name/city stripped)
    keys = [_template_key(r.get("personalization_line", ""), r.get("business_name", ""), r.get("city", "")) for r in norm_rows]
    top_template, top_count = Counter(keys).most_common(1)[0] if keys else ("", 0)
    if len(norm_rows) >= 10 and top_count >= max(5, int(0.55 * len(norm_rows))):
        warnings.append(
            {
                "row": 0,
                "level": "warn",
                "code": "template_monoculture",
                "message": f"{top_count}/{len(norm_rows)} lines share the same sentence shape after name/city swap — consider AI or niche-specific variants",
            }
        )

    return errors, warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", type=Path, help="Path to Smartlead CSV")
    ap.add_argument("--json-out", type=Path, default=None, help="Write full report JSON here")
    ap.add_argument("--warn-only", action="store_true", help="Exit 0 even when errors listed (not recommended)")
    args = ap.parse_args()

    with args.csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    errors, warnings = validate_rows(rows)

    print(f"File: {args.csv_path}")
    print(f"Rows: {len(rows)}")
    print(f"Errors: {len(errors)}  Warnings: {len(warnings)}")

    for item in errors[:50]:
        print(f"  ERROR row {item['row']}: [{item.get('code')}] {item['message']}")
    if len(errors) > 50:
        print(f"  ... and {len(errors) - 50} more errors")

    for item in warnings[:40]:
        print(f"  WARN row {item['row']}: [{item.get('code')}] {item['message']}")
    if len(warnings) > 40:
        print(f"  ... and {len(warnings) - 40} more warnings")

    if args.json_out:
        report = {
            "csv_path": str(args.csv_path),
            "row_count": len(rows),
            "errors": errors,
            "warnings": warnings,
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")

    if errors and not args.warn_only:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
