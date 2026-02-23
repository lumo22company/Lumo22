#!/usr/bin/env python3
"""
Insert a test appointment via direct Postgres (bypasses RLS).
Uses DATABASE_URL from .env. Requires psycopg2: pip install psycopg2-binary
Usage: python3 scripts/insert_test_appointment_db.py [YYYY-MM-DD]
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / ".env")

def main():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL must be set in .env")
        print("Get it: Supabase → Project Settings → Database → Connection string (URI)")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    date_str = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if date_str:
        try:
            day = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            print("ERROR: Use YYYY-MM-DD")
            sys.exit(1)
    else:
        day = (datetime.now() + timedelta(days=1)).date()

    slot_start = f"{day}T14:00:00"
    slot_end = f"{day}T15:00:00"

    sql = """
    INSERT INTO public.appointments (slot_start, slot_end)
    VALUES (%s::timestamptz, %s::timestamptz)
    RETURNING id, slot_start, slot_end;
    """
    print(f"Inserting test appointment: {day} at 14:00 (2pm-3pm)...")
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, (slot_start, slot_end))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            print(f"Done. Inserted: id={row[0]}")
            print("Go to /book-demo, choose that date, turn on 'Group appointments together'.")
        else:
            print("Insert completed but no row returned.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
