#!/usr/bin/env python3
"""
Run multi-niche lead pipeline:
  1) Pull raw CSV from Apify task
  2) Dedupe emails
  3) Enrich personalization lines
  4) Validate Smartlead CSV

This script intentionally stops before Smartlead API import because endpoint
contracts vary by account/workspace. Use the generated *_ready.csv files for
import, or add API import once your endpoint contract is confirmed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from glob import glob

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
EXPORTS_DIR = ROOT / "exports"
SEEN_REGISTRY_PATH = EXPORTS_DIR / "seen_leads_registry.csv"

# Load .env automatically so APIFY_TOKEN works without shell export.
load_dotenv(dotenv_path=ROOT / ".env")


def _run(cmd: list[str]) -> None:
    print(f"[cmd] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def _download_apify_csv(task_id: str, token: str, out_csv: Path) -> None:
    q = urllib.parse.urlencode({"token": token, "format": "csv", "clean": "1"})
    url = f"https://api.apify.com/v2/actor-tasks/{task_id}/run-sync-get-dataset-items?{q}"
    print(f"[apify] downloading task={task_id} -> {out_csv}")
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=420) as resp:
                body = resp.read()
            break
        except Exception as e:  # pragma: no cover - network transient
            last_err = e
            if attempt == 3:
                raise
            print(f"[apify] retry {attempt}/3 after error: {e}")
            time.sleep(2.0 * attempt)
    if last_err is not None and "body" not in locals():
        raise last_err
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.write_bytes(body)


def _headers(csv_path: Path) -> list[str]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or [])


def _build_smartlead_shape_from_apify(raw_csv: Path, out_csv: Path) -> None:
    """
    Convert wide Apify Maps CSV -> minimal Smartlead-like CSV expected by existing scripts.
    """
    with raw_csv.open(newline="", encoding="utf-8-sig") as f_in:
        rows = list(csv.DictReader(f_in))
    if not rows:
        raise SystemExit(f"No rows in raw Apify CSV: {raw_csv}")

    out_rows: list[dict[str, str]] = []
    for r in rows:
        business = (r.get("title") or "").strip()
        city = (r.get("city") or "").strip()
        niche = (r.get("categoryName") or "").strip()
        website = (r.get("website") or "").strip()
        out_rows.append(
            {
                "business_name": business,
                "first_name": "",
                "email": "",
                "place_id": (r.get("placeId") or "").strip(),
                "city": city,
                "niche": niche,
                "website": website,
                "personalization_line": "",
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(
            f_out,
            fieldnames=[
                "business_name",
                "first_name",
                "email",
                "place_id",
                "city",
                "niche",
                "website",
                "personalization_line",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)


def _apply_probed_email(probed_csv: Path, out_csv: Path) -> None:
    with probed_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"No rows after email probing: {probed_csv}")
    fields = list(rows[0].keys())
    if "email" not in fields or "enrichment_best_email" not in fields:
        raise SystemExit("Probed CSV missing expected columns: email and enrichment_best_email")

    for r in rows:
        if not (r.get("email") or "").strip():
            r["email"] = (r.get("enrichment_best_email") or "").strip()

    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _count_rows(csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return sum(1 for _ in reader)


def _norm(s: str) -> str:
    return (s or "").strip()


def _norm_host(url: str) -> str:
    u = (url or "").strip().lower()
    if u.startswith("http://"):
        u = u[len("http://") :]
    if u.startswith("https://"):
        u = u[len("https://") :]
    if u.startswith("www."):
        u = u[len("www.") :]
    return u.rstrip("/")


def _lead_key(row: dict[str, str]) -> str:
    email = _norm(row.get("email", "")).casefold()
    if email:
        return f"email:{email}"
    place_id = _norm(row.get("place_id", ""))
    if place_id:
        return f"place:{place_id}"
    website = _norm_host(row.get("website", ""))
    business = _norm(row.get("business_name", "")).casefold()
    city = _norm(row.get("city", "")).casefold()
    if website and business and city:
        return f"site_name_city:{website}|{business}|{city}"
    if website and business:
        return f"site_name:{website}|{business}"
    return ""


def _iter_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _collect_seen_keys(extra_globs: list[str], slug: str) -> set[str]:
    seen: set[str] = set()

    # 1) persistent registry
    for r in _iter_csv_rows(SEEN_REGISTRY_PATH):
        reg_slug = _norm(r.get("slug", ""))
        if reg_slug and reg_slug != slug:
            continue
        k = _norm(r.get("lead_key", ""))
        if k:
            seen.add(k)

    # 2) existing exports from prior runs/import prep
    default_patterns = [
        "smartlead_ready_*.csv",
        "smartlead_super_safe_*.csv",
        "SMARTLEAD_IMPORT_*.csv",
    ]
    patterns = default_patterns + extra_globs
    for pat in patterns:
        for p in sorted(glob(str(EXPORTS_DIR / pat))):
            fname = Path(p).name
            if fname.startswith("smartlead_ready_") or fname.startswith("smartlead_new_only_"):
                if slug not in fname:
                    continue
            for r in _iter_csv_rows(Path(p)):
                k = _lead_key(r)
                if k:
                    seen.add(k)

    return seen


def _niche_keyword_filters(slug: str, niche_cfg: dict) -> tuple[list[str], list[str]]:
    include = [str(x).strip().lower() for x in niche_cfg.get("include_keywords", []) if str(x).strip()]
    exclude = [str(x).strip().lower() for x in niche_cfg.get("exclude_keywords", []) if str(x).strip()]
    if include or exclude:
        return include, exclude
    if "fitness" in slug:
        include = [
            "gym",
            "fitness",
            "personal trainer",
            "pilates",
            "yoga",
            "crossfit",
            "hyrox",
            "boxing",
            "kickboxing",
            "pole",
            "barre",
            "strength",
        ]
        exclude = [
            "student housing",
            "drama school",
            "art school",
            "theatre school",
            "car hire",
            "hotel",
            "restaurant",
            "cafe",
            "estate agent",
        ]
    elif "aesthetic" in slug or "beauty" in slug:
        include = [
            "aesthetic",
            "aesthetics",
            "beauty",
            "skin",
            "skincare",
            "laser",
            "cosmetic",
            "clinic",
            "med spa",
            "medical spa",
            "facial",
            "nail",
            "lash",
            "brow",
            "spa",
            "salon",
        ]
        exclude = [
            "hospital",
            "doctor",
            "gp",
            "dentist",
            "veterinary",
            "pharmacy",
            "training provider",
            "school",
            "college",
            "restaurant",
            "cafe",
            "hotel",
        ]
    return include, exclude


def _passes_niche_filter(row: dict[str, str], slug: str, niche_cfg: dict) -> bool:
    include, exclude = _niche_keyword_filters(slug, niche_cfg)
    if not include and not exclude:
        return True
    blob = " ".join(
        [
            _norm(row.get("niche", "")).lower(),
            _norm(row.get("business_name", "")).lower(),
            _norm(row.get("website", "")).lower(),
        ]
    )
    if include and not any(k in blob for k in include):
        return False
    if exclude and any(k in blob for k in exclude):
        return False
    return True


def _write_new_only_and_update_registry(
    *,
    ready_csv: Path,
    new_only_csv: Path,
    seen_before: set[str],
    slug: str,
    niche_cfg: dict,
) -> tuple[int, int]:
    rows = _iter_csv_rows(ready_csv)
    if not rows:
        raise SystemExit(f"No rows in ready CSV: {ready_csv}")
    fields = list(rows[0].keys())

    fresh_rows: list[dict[str, str]] = []
    new_keys: list[str] = []
    skipped_existing = 0
    for r in rows:
        if not _passes_niche_filter(r, slug=slug, niche_cfg=niche_cfg):
            continue
        k = _lead_key(r)
        if not k:
            # Keep rows with missing keys so they can be manually reviewed.
            fresh_rows.append(r)
            continue
        if k in seen_before:
            skipped_existing += 1
            continue
        fresh_rows.append(r)
        new_keys.append(k)
        seen_before.add(k)

    new_only_csv.parent.mkdir(parents=True, exist_ok=True)
    with new_only_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(fresh_rows)

    # Append net-new keys to persistent registry
    reg_exists = SEEN_REGISTRY_PATH.exists()
    with SEEN_REGISTRY_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lead_key", "slug", "recorded_at"])
        if not reg_exists:
            w.writeheader()
        now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
        for k in new_keys:
            w.writerow({"lead_key": k, "slug": slug, "recorded_at": now})

    return len(fresh_rows), skipped_existing


def _split_chunks(items: list[dict], n: int) -> list[list[dict]]:
    if n <= 0:
        return [items]
    return [items[i : i + n] for i in range(0, len(items), n)]


def _smartlead_payload_row(row: dict[str, str]) -> dict:
    email = _norm(row.get("email", ""))
    custom_fields: dict[str, str] = {}
    for k, v in row.items():
        if k in ("email", "first_name", "firstName", "last_name", "lastName"):
            continue
        vv = _norm(v)
        if vv:
            custom_fields[k] = vv
    return {
        "email": email,
        "first_name": _norm(row.get("first_name", "") or row.get("firstName", "")),
        "last_name": _norm(row.get("last_name", "") or row.get("lastName", "")),
        "custom_fields": custom_fields,
    }


def _import_new_only_to_smartlead(
    *,
    new_only_csv: Path,
    campaign_id: str,
    api_key: str,
    batch_size: int = 50,
    dry_run: bool = False,
) -> dict[str, int | str]:
    rows = _iter_csv_rows(new_only_csv)
    leads = []
    for r in rows:
        if _norm(r.get("email", "")):
            leads.append(_smartlead_payload_row(r))

    if dry_run:
        return {
            "attempted_rows": len(rows),
            "attempted_with_email": len(leads),
            "imported_count": 0,
            "failed_count": 0,
            "status": "dry_run",
        }
    if not leads:
        return {
            "attempted_rows": len(rows),
            "attempted_with_email": 0,
            "imported_count": 0,
            "failed_count": 0,
            "status": "no_email_rows",
        }

    endpoint = (
        f"https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/leads"
        f"?api_key={urllib.parse.quote(api_key)}"
    )
    imported = 0
    failed = 0
    for chunk in _split_chunks(leads, batch_size):
        payload = json.dumps({"lead_list": chunk}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                _ = resp.read()
            imported += len(chunk)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"[smartlead] HTTP {e.code} for chunk size {len(chunk)}: {body[:400]}")
            failed += len(chunk)
        except Exception as e:
            print(f"[smartlead] request failed for chunk size {len(chunk)}: {e}")
            failed += len(chunk)

    return {
        "attempted_rows": len(rows),
        "attempted_with_email": len(leads),
        "imported_count": imported,
        "failed_count": failed,
        "status": "ok" if failed == 0 else "partial_failure",
    }


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Missing config: {path}\n"
            "Copy configs/niches.example.json to configs/niches.json and fill IDs."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/niches.json", help="Path to niches config JSON")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="Date suffix for output files (YYYY-MM-DD)")
    ap.add_argument("--skip-apify", action="store_true", help="Skip Apify download and use existing raw CSV files")
    ap.add_argument("--limit-niches", type=int, default=0, help="Process at most N enabled niches (0 = all)")
    ap.add_argument("--only-slug", default="", help="Process only one niche slug (e.g. fitness_bath)")
    ap.add_argument("--ignore-seen", action="store_true", help="Ignore seen registry/history and export all filtered rows")
    ap.add_argument("--probe-delay", type=float, default=0.25, help="Website probe delay seconds for email enrichment")
    ap.add_argument("--probe-timeout", type=int, default=6, help="Per-request timeout seconds for website probing")
    ap.add_argument(
        "--seen-glob",
        action="append",
        default=[],
        help="Extra exports glob(s) to treat as already processed (repeatable)",
    )
    ap.add_argument("--import-smartlead", action="store_true", help="POST new_only rows to Smartlead campaign API")
    ap.add_argument("--dry-run-import", action="store_true", help="With --import-smartlead, print import intent only")
    ap.add_argument("--import-batch-size", type=int, default=50, help="Smartlead import batch size (default 50)")
    args = ap.parse_args()

    cfg = _load_config((ROOT / args.config).resolve())
    defaults = cfg.get("defaults", {})
    niches = [n for n in cfg.get("niches", []) if n.get("enabled", True)]
    if args.only_slug.strip():
        target = args.only_slug.strip()
        niches = [n for n in niches if str(n.get("slug", "")).strip() == target]
    if args.limit_niches > 0:
        niches = niches[: args.limit_niches]
    if not niches:
        raise SystemExit("No enabled niches found in config.")

    apify_token = os.getenv("APIFY_TOKEN", "").strip() or os.getenv("APIFY_API_TOKEN", "").strip()
    use_ai = bool(defaults.get("use_ai", True))
    vertical = str(defaults.get("vertical", "auto"))
    drop_wix_sentry = bool(defaults.get("drop_wix_sentry", True))
    smartlead_api_key = os.getenv("SMARTLEAD_API_KEY", "").strip()

    summary: list[dict[str, str | int]] = []
    for niche in niches:
        slug = str(niche["slug"]).strip()
        if not slug:
            raise SystemExit("Each niche needs a non-empty slug.")
        seen_keys = set() if args.ignore_seen else _collect_seen_keys(extra_globs=args.seen_glob, slug=slug)

        raw_csv = EXPORTS_DIR / f"apify_raw_{slug}_{args.date}.csv"
        normalized_csv = EXPORTS_DIR / f"apify_normalized_{slug}_{args.date}.csv"
        probed_csv = EXPORTS_DIR / f"apify_email_probed_{slug}_{args.date}.csv"
        pre_dedupe_csv = EXPORTS_DIR / f"apify_prededupe_{slug}_{args.date}.csv"
        deduped_csv = EXPORTS_DIR / f"apify_deduped_{slug}_{args.date}.csv"
        ready_csv = EXPORTS_DIR / f"smartlead_ready_{slug}_{args.date}.csv"
        new_only_csv = EXPORTS_DIR / f"smartlead_new_only_{slug}_{args.date}.csv"
        report_json = EXPORTS_DIR / f"validation_{slug}_{args.date}.json"

        task_id = str(niche.get("apify_task_id", "")).strip()
        if not args.skip_apify:
            if not task_id:
                raise SystemExit(f"[{slug}] missing apify_task_id in config")
            if not apify_token:
                raise SystemExit("APIFY_TOKEN is required (set it in .env or export it in your shell).")
            _download_apify_csv(task_id=task_id, token=apify_token, out_csv=raw_csv)
        elif not raw_csv.exists():
            raise SystemExit(f"[{slug}] --skip-apify used but raw file missing: {raw_csv}")

        raw_headers = {h.strip() for h in _headers(raw_csv)}
        if "email" in raw_headers and "business_name" in raw_headers:
            pre_dedupe_source = raw_csv
        else:
            # Map actor output to repo's expected shape, then probe websites for public emails.
            _build_smartlead_shape_from_apify(raw_csv=raw_csv, out_csv=normalized_csv)
            _run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "enrich_csv_emails_from_websites.py"),
                    str(normalized_csv),
                    "--out",
                    str(probed_csv),
                    "--delay",
                    str(args.probe_delay),
                    "--timeout",
                    str(args.probe_timeout),
                ]
            )
            _apply_probed_email(probed_csv=probed_csv, out_csv=pre_dedupe_csv)
            pre_dedupe_source = pre_dedupe_csv

        dedupe_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "dedupe_smartlead_csv.py"),
            str(pre_dedupe_source),
            "--out",
            str(deduped_csv),
        ]
        if drop_wix_sentry:
            dedupe_cmd.append("--drop-wix-sentry")
        _run(dedupe_cmd)

        enrich_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "enrich_personalization_fitness_from_apify.py"),
            str(deduped_csv),
            "--out",
            str(ready_csv),
            "--vertical",
            vertical,
        ]
        if use_ai:
            enrich_cmd.append("--use-ai")
        _run(enrich_cmd)

        _run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "validate_smartlead_csv.py"),
                str(ready_csv),
                "--json-out",
                str(report_json),
            ]
        )
        new_only_rows, skipped_existing = _write_new_only_and_update_registry(
            ready_csv=ready_csv,
            new_only_csv=new_only_csv,
            seen_before=seen_keys,
            slug=slug,
            niche_cfg=niche,
        )

        summary.append(
            {
                "slug": slug,
                "raw_rows": _count_rows(raw_csv),
                "ready_rows": _count_rows(ready_csv),
                "new_only_rows": new_only_rows,
                "skipped_existing_rows": skipped_existing,
                "raw_csv": str(raw_csv.relative_to(ROOT)),
                "ready_csv": str(ready_csv.relative_to(ROOT)),
                "new_only_csv": str(new_only_csv.relative_to(ROOT)),
                "validation_report": str(report_json.relative_to(ROOT)),
                "smartlead_campaign_id": str(niche.get("smartlead_campaign_id", "")),
            }
        )

        if args.import_smartlead:
            campaign_id = str(niche.get("smartlead_campaign_id", "")).strip()
            if not campaign_id:
                raise SystemExit(f"[{slug}] missing smartlead_campaign_id in config")
            if not smartlead_api_key:
                raise SystemExit(
                    "SMARTLEAD_API_KEY is required when --import-smartlead is used. "
                    "If your Smartlead plan does not support API keys, run without --import-smartlead "
                    "and manually upload the smartlead_new_only CSV shown in the summary."
                )
            import_result = _import_new_only_to_smartlead(
                new_only_csv=new_only_csv,
                campaign_id=campaign_id,
                api_key=smartlead_api_key,
                batch_size=args.import_batch_size,
                dry_run=args.dry_run_import,
            )
            summary[-1]["smartlead_import_status"] = str(import_result["status"])
            summary[-1]["smartlead_imported_count"] = int(import_result["imported_count"])
            summary[-1]["smartlead_import_failed_count"] = int(import_result["failed_count"])

    print("\n=== Pipeline Summary ===")
    for item in summary:
        base = (
            f"- {item['slug']}: raw={item['raw_rows']} ready={item['ready_rows']} "
            f"new_only={item['new_only_rows']} skipped_existing={item['skipped_existing_rows']} "
            f"new_only_csv={item['new_only_csv']}"
        )
        if "smartlead_import_status" in item:
            base += (
                f" import_status={item['smartlead_import_status']} "
                f"imported={item.get('smartlead_imported_count', 0)} "
                f"failed={item.get('smartlead_import_failed_count', 0)}"
            )
        print(base)

    # Always print a manual upload guide (useful when API import is plan-gated).
    print("\n=== Manual Upload Checklist ===")
    for item in summary:
        print(
            f"- Campaign {item['smartlead_campaign_id']} ({item['slug']}): "
            f"upload `{item['new_only_csv']}` ({item['new_only_rows']} rows)"
        )
    print("  Smartlead -> Campaign -> Leads -> Import CSV -> map fields -> start/unpause.")
    out = EXPORTS_DIR / f"pipeline_summary_{args.date}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote summary: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
