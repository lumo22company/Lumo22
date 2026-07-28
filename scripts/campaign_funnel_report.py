#!/usr/bin/env python3
"""
Campaign funnel report: where signups came from and how far they got.

Read-only. Needs SUPABASE_SERVICE_ROLE_KEY in .env — caption_orders RLS denies the anon key
(database_caption_orders_rls_harden_service_role.sql), and an anon read silently returns zero
rows, which reads exactly like "no signups". This script refuses to run on the anon key rather
than print a misleading empty report.

Run: python3 scripts/campaign_funnel_report.py [--days 30] [--emails]

  --days N   window to report on (default 30)
  --emails   show full addresses instead of masked ones (for following leads up)
"""
import argparse
import base64
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

SAMPLE_PRODUCT_TYPE = "sample_3"


def _key_role(key: str) -> str:
    """Read the role claim out of a Supabase JWT without printing the key."""
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role") or "unknown"
    except Exception:
        return "unknown"


def _mask(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return e or "(none)"
    name, _, domain = e.partition("@")
    return f"{name[:2]}***@{domain}"


def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--emails", action="store_true", help="show full email addresses")
    args = ap.parse_args()

    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in .env.")
        print("  Supabase Dashboard → Project Settings → API → service_role key.")
        print("  The anon key cannot read caption_orders (RLS denies it) and returns 0 rows silently.")
        sys.exit(1)
    role = _key_role(key)
    if role != "service_role":
        print(f"ERROR: SUPABASE_SERVICE_ROLE_KEY has role '{role}', expected 'service_role'.")
        print("  Reading with that key would return 0 rows and look like zero signups.")
        sys.exit(1)

    from supabase import create_client

    sb = create_client(url, key)
    since = datetime.now(timezone.utc) - timedelta(days=args.days)

    select = (
        "id,created_at,customer_email,product_type,currency,status,delivered_at,"
        "stripe_session_id,upgraded_from_token,token,intake"
    )
    try:
        rows = (
            sb.table("caption_orders")
            .select(select + ",source")
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        have_source = True
    except Exception as e:
        # Column not migrated yet (run_caption_orders_source_migration.py).
        if "source" not in str(e):
            raise
        rows = (
            sb.table("caption_orders")
            .select(select)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        have_source = False

    show = (lambda e: e) if args.emails else _mask
    samples = [r for r in rows if (r.get("product_type") or "standard") == SAMPLE_PRODUCT_TYPE]
    paid = [r for r in rows if (r.get("product_type") or "standard") != SAMPLE_PRODUCT_TYPE]
    upgrades = [r for r in paid if (r.get("upgraded_from_token") or "").strip()]

    print(f"=== LAST {args.days} DAYS ({since.date()} → {datetime.now(timezone.utc).date()}) ===")
    print(f"sample signups : {len(samples)}")
    print(f"paid orders    : {len(paid)}  (of which upgraded from a sample: {len(upgrades)})")
    if samples:
        rate = 100.0 * len(upgrades) / len(samples)
        print(f"sample → paid  : {rate:.1f}%")
    if not have_source:
        print("\nNOTE: caption_orders.source not migrated yet — no campaign attribution available.")
        print("      Run: python3 run_caption_orders_source_migration.py")

    def _bucket(order):
        """How far down the funnel this row got."""
        intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
        status = (order.get("status") or "").strip()
        if order.get("delivered_at") or status == "delivered":
            return "3. delivered"
        if intake:
            return "2. form submitted"
        return "1. signed up only"

    print("\n--- SAMPLE FUNNEL ---")
    for stage, n in sorted(Counter(_bucket(r) for r in samples).items()):
        print(f"  {stage:<20} {n}")

    if have_source:
        print("\n--- BY SOURCE ---")
        by_source = defaultdict(lambda: {"samples": 0, "paid": 0, "delivered": 0})
        for r in samples:
            key_ = (r.get("source") or "(direct/unknown)")
            by_source[key_]["samples"] += 1
            if _bucket(r) == "3. delivered":
                by_source[key_]["delivered"] += 1
        for r in paid:
            by_source[(r.get("source") or "(direct/unknown)")]["paid"] += 1
        print(f"  {'source':<34} {'samples':>8} {'delivered':>10} {'paid':>6}")
        for key_, v in sorted(by_source.items(), key=lambda kv: -kv[1]["samples"]):
            print(f"  {key_[:34]:<34} {v['samples']:>8} {v['delivered']:>10} {v['paid']:>6}")

    print("\n--- BY CURRENCY (proxy for region) ---")
    print(f"  samples: {dict(Counter((r.get('currency') or '?') for r in samples))}")
    print(f"  paid   : {dict(Counter((r.get('currency') or '?') for r in paid))}")

    print("\n--- SAMPLE SIGNUPS (newest first) ---")
    for r in samples[:80]:
        dt = _parse_dt(r.get("created_at"))
        intake = r.get("intake") if isinstance(r.get("intake"), dict) else {}
        print(
            f"  {str(dt)[:16]:<17} {(r.get('currency') or '?'):>3} "
            f"{show(r.get('customer_email')):<32} {_bucket(r):<18} "
            f"src={(r.get('source') or '-') if have_source else 'n/a':<22} "
            f"biz={(intake.get('business_name') or '-')[:24]}"
        )

    print("\n--- PAID ORDERS (newest first) ---")
    for r in paid[:80]:
        dt = _parse_dt(r.get("created_at"))
        print(
            f"  {str(dt)[:16]:<17} {(r.get('currency') or '?'):>3} "
            f"{show(r.get('customer_email')):<32} {(r.get('status') or '-'):<16} "
            f"src={(r.get('source') or '-') if have_source else 'n/a':<22} "
            f"{'(upgraded from sample)' if (r.get('upgraded_from_token') or '').strip() else ''}"
        )


if __name__ == "__main__":
    main()
