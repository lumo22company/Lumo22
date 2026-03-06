#!/usr/bin/env python3
"""
Add delivered_at, upgraded_from_token, scheduled_delivery_at to caption_orders.
Required for: first subscription pack delivered 30 days after one-off (upgrade flow).
Uses DATABASE_URL from .env. Or run database_caption_orders_upgrade_schedule.sql in Supabase SQL Editor.

Run: python3 run_upgrade_schedule_migration.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def main():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        print("Alternatively, run database_caption_orders_upgrade_schedule.sql in Supabase SQL Editor.")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = Path(__file__).parent / "database_caption_orders_upgrade_schedule.sql"
    if not sql_file.exists():
        print(f"ERROR: {sql_file} not found")
        sys.exit(1)
    sql = sql_file.read_text()

    print("Connecting to Supabase...")
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("Done. caption_orders now has delivered_at, upgraded_from_token, scheduled_delivery_at.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
