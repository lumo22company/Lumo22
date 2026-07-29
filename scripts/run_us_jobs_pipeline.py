#!/usr/bin/env python3
"""
One-command US jobs email pipeline (no bash). Prints immediately.

  python3 scripts/run_us_jobs_pipeline.py
  python3 scripts/run_us_jobs_pipeline.py --date 2026-07-02 --apify-only
  python3 scripts/run_us_jobs_pipeline.py --probe-limit 10   # quick test
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent


def _run(cmd: list[str], label: str) -> None:
    print(f"\n>>> {label}", flush=True)
    print("    " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def _count_emails(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return sum(
        1 for r in rows if (r.get("email") or r.get("enrichment_best_email") or "").strip()
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default="2026-07-02")
    ap.add_argument("--apify-only", action="store_true", help="Skip slow local probe; use Apify only")
    ap.add_argument("--no-apify", action="store_true", help="Local probe only")
    ap.add_argument("--probe-limit", type=int, default=None, help="Max SMB rows for local probe")
    ap.add_argument("--apify-limit", type=int, default=None, help="Max rows for Apify fallback")
    args = ap.parse_args()

    py = sys.executable
    date = args.date
    exports = ROOT / "exports"
    ready = exports / f"smartlead_ready_jobs_us_{date}.csv"
    websites = exports / f"jobs_us_with_websites_{date}.csv"
    smb = exports / f"jobs_us_smb_{date}.csv"
    emails = exports / f"jobs_us_with_emails_{date}.csv"
    emails_apify = exports / f"jobs_us_with_emails_apify_{date}.csv"
    import_csv = exports / f"smartlead_us_import_{date}.csv"

    print(f"US jobs pipeline | date={date} | repo={ROOT}", flush=True)
    if not ready.exists():
        raise SystemExit(f"Missing {ready} — run scrape import first.")

    if not websites.exists():
        _run(
            [
                py,
                "-u",
                str(SCRIPTS / "find_company_websites.py"),
                str(ready),
                "--out",
                str(websites),
                "--skip-recruiters",
                "--country",
                "US",
                "--delay",
                "1.0",
            ],
            "Step 1/5: Find websites",
        )
    else:
        print(f"\n>>> Step 1/5: Websites exist — skip ({websites})", flush=True)

    _run(
        [py, str(SCRIPTS / "filter_smb_jobs_csv.py"), str(websites), "--out", str(smb)],
        "Step 2/5: SMB filter",
    )

    final_emails = emails
    if not args.apify_only:
        probe_cmd = [
            py,
            "-u",
            str(SCRIPTS / "enrich_csv_emails_from_websites.py"),
            str(smb),
            "--out",
            str(emails),
            "--delay",
            "0.5",
            "--timeout",
            "15",
        ]
        if args.probe_limit is not None:
            probe_cmd.extend(["--limit", str(args.probe_limit)])
        _run(probe_cmd, "Step 3/5: Local email probe")
    else:
        print("\n>>> Step 3/5: Skipped local probe (--apify-only)", flush=True)
        # Copy SMB → emails so Apify has input shape
        emails.write_bytes(smb.read_bytes())
        final_emails = emails

    if not args.no_apify:
        apify_cmd = [
            py,
            str(SCRIPTS / "enrich_emails_apify.py"),
            str(final_emails),
            "--out",
            str(emails_apify),
        ]
        if args.apify_limit is not None:
            apify_cmd.extend(["--limit", str(args.apify_limit)])
        try:
            _run(apify_cmd, "Step 4/5: Apify email enrich")
            final_emails = emails_apify
        except subprocess.CalledProcessError:
            print("Apify step failed — using local probe output only.", flush=True)

    _run(
        [
            py,
            str(SCRIPTS / "prepare_smartlead_jobs_import.py"),
            str(final_emails),
            "--out",
            str(import_csv),
        ],
        "Step 5/5: Smartlead import CSV",
    )

    n = _count_emails(import_csv)
    print(f"\n=== DONE ===", flush=True)
    print(f"Import file: {import_csv}", flush=True)
    print(f"Leads with email: {n}", flush=True)
    if n == 0:
        print(
            "\nNo emails found. Try: python3 scripts/run_us_jobs_pipeline.py --apify-only",
            flush=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
