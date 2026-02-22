#!/usr/bin/env python3
"""
Run customers + auto_reply migrations in one go.
Requires DATABASE_URL in .env (Supabase → Project Settings → Database → Connection string → URI).
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

def run_sql_file(conn, filename: str, label: str) -> bool:
    path = Path(__file__).parent / filename
    if not path.exists():
        print(f"  SKIP: {filename} not found")
        return True
    try:
        sql = path.read_text()
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        print(f"  OK: {label}")
        return True
    except Exception as e:
        print(f"  ERROR ({label}): {e}")
        return False

def main():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        print("Add it from: Supabase Dashboard → Project Settings → Database → Connection string → URI")
        print("Then run: python3 run_account_and_auto_reply_migrations.py")
        sys.exit(1)
    url = "".join(c for c in url if ord(c) >= 32).strip()

    try:
        import psycopg2
    except ImportError:
        print("ERROR: pip install psycopg2-binary")
        sys.exit(1)

    print("Connecting to Supabase...")
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True

        print("Running migrations:")
        ok1 = run_sql_file(conn, "database_customers.sql", "customers table")
        ok2 = run_sql_file(conn, "database_front_desk_auto_reply.sql", "auto_reply columns")

        conn.close()
        if ok1 and ok2:
            print("Done. Account dashboard and auto-reply are ready.")
        else:
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
