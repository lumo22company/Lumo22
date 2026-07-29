#!/usr/bin/env python3
"""
Finish US jobs email pipeline — local probe first, Apify optional fallback.

  python3 scripts/us_jobs_finish.py
  python3 scripts/us_jobs_finish.py --limit 50 --skip-apify
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DATE = "2026-07-02"


def _count_emails(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        return sum(
            1
            for r in csv.DictReader(f)
            if (r.get("email") or r.get("enrichment_best_email") or "").strip()
        )


def main() -> None:
    print("us_jobs_finish: START", flush=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=DATE)
    ap.add_argument("--limit", type=int, default=50, help="Max SMB rows to probe locally")
    ap.add_argument("--skip-apify", action="store_true", help="Skip Apify (use if token 401)")
    args = ap.parse_args()

    py = sys.executable
    exports = ROOT / "exports"
    websites = exports / f"jobs_us_with_websites_{args.date}.csv"
    smb = exports / f"jobs_us_smb_{args.date}.csv"
    emails_local = exports / f"jobs_us_with_emails_{args.date}.csv"
    emails_apify = exports / f"jobs_us_with_emails_apify_{args.date}.csv"
    import_csv = exports / f"smartlead_us_import_{args.date}.csv"
    log = exports / f"us_jobs_finish_{args.date}.log"

    if not websites.exists():
        raise SystemExit(f"Missing {websites}")

    def step(label: str, cmd: list[str], optional: bool = False) -> bool:
        line = f"\n>>> {label}\n"
        print(line, end="", flush=True)
        with log.open("a", encoding="utf-8") as lf:
            lf.write(line)
            lf.write(" ".join(cmd) + "\n")
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            if optional:
                print(f"  (optional step failed — continuing)", flush=True)
                return False
            raise SystemExit(f"Step failed: {label}")
        return True

    print(f"Repo: {ROOT}", flush=True)
    print(f"Log:  {log}", flush=True)

    step(
        "SMB filter",
        [py, str(SCRIPTS / "filter_smb_jobs_csv.py"), str(websites), "--out", str(smb)],
    )

    probe_cmd = [
        py,
        "-u",
        str(SCRIPTS / "enrich_csv_emails_from_websites.py"),
        str(smb),
        "--out",
        str(emails_local),
        "--delay",
        "0.5",
        "--timeout",
        "15",
    ]
    if args.limit:
        probe_cmd.extend(["--limit", str(args.limit)])
    step("Local email probe (SMB)", probe_cmd)

    final = emails_local
    n_local = _count_emails(emails_local)
    print(f"Local probe found {n_local} emails", flush=True)

    if not args.skip_apify and n_local < 10:
        print("Trying Apify fallback (needs valid APIFY_TOKEN in .env)...", flush=True)
        if step(
            "Apify emails",
            [
                py,
                "-u",
                str(SCRIPTS / "enrich_emails_apify.py"),
                str(emails_local),
                "--out",
                str(emails_apify),
                "--limit",
                str(min(args.limit, 25)),
            ],
            optional=True,
        ):
            if _count_emails(emails_apify) > n_local:
                final = emails_apify

    n_final = _count_emails(final)
    if n_final == 0:
        print("\n=== STOPPED === 0 emails found.", flush=True)
        print(
            "Apify returned HTTP 401 last run — update APIFY_TOKEN at "
            "https://console.apify.com/account/integrations",
            flush=True,
        )
        print(
            "Re-run local probe on more rows: "
            "python3 scripts/us_jobs_finish.py --skip-apify --limit 168",
            flush=True,
        )
        sys.exit(1)

    step(
        "Smartlead import CSV",
        [
            py,
            str(SCRIPTS / "prepare_smartlead_jobs_import.py"),
            str(final),
            "--out",
            str(import_csv),
        ],
    )

    with import_csv.open(newline="", encoding="utf-8-sig") as f:
        n = sum(1 for r in csv.DictReader(f) if (r.get("email") or "").strip())

    print(f"\n=== DONE === Leads with email: {n}", flush=True)
    print(f"Import: {import_csv}", flush=True)


if __name__ == "__main__":
    main()
