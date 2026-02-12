#!/usr/bin/env python3
"""
Run database_customers_and_auto_reply.sql (customers, auto_reply, stripe ids, marketing_opt_in, password reset).
Requires DATABASE_URL in .env (Supabase → Project Settings → Database → Connection string → URI).
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
        print("Add it from: Supabase Dashboard → Project Settings → Database → Connection string → URI")
        print("Or run database_customers_and_auto_reply.sql manually in Supabase SQL Editor.")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: pip install psycopg2-binary")
        sys.exit(1)

    sql_file = Path(__file__).parent / "database_customers_and_auto_reply.sql"
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
        print("Done. Customers, auto_reply, stripe IDs, marketing_opt_in, and password_reset columns are ready.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
