#!/usr/bin/env python3
"""
Add enquiry_types, opening_hours, reply_same_day, reply_24h, tone, good_lead_rules to front_desk_setups.
Uses DATABASE_URL from .env (Supabase → Project Settings → Database → Connection string → URI).
Or run database_front_desk_preferences.sql in Supabase SQL Editor.
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
        print("Run this script with DATABASE_URL set, or run database_front_desk_preferences.sql in Supabase SQL Editor.")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = Path(__file__).parent / "database_front_desk_preferences.sql"
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
        print("Done. enquiry_types, opening_hours, reply_same_day, reply_24h, tone, good_lead_rules columns added.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
