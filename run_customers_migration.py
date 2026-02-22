#!/usr/bin/env python3
"""
Create the customers table in Supabase for Lumo 22 account dashboard.
Uses DATABASE_URL (Postgres connection string) from .env.

Get your connection string: Supabase Dashboard → Project Settings → Database → Connection string → URI.
"""
import os
import sys
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv
load_dotenv()

def main():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        print("Get it from: Supabase Dashboard → Settings → Database → Connection string (URI)")
        sys.exit(1)
    # Remove any newline/control chars
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = Path(__file__).parent / "database_customers.sql"
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
        print("Done. customers table is ready.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
