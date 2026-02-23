#!/usr/bin/env python3
"""
Add include_stories to caption_orders in Supabase.
Uses DATABASE_URL (Postgres connection string) from .env.

Get it from: Supabase Dashboard → Project Settings → Database → Connection string → URI.
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
        print("Get it from: Supabase Dashboard → Settings → Database → Connection string (URI)")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = Path(__file__).parent / "database_caption_orders_stories.sql"
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
        print("Done. caption_orders now has include_stories column.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
