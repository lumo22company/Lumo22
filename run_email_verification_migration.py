#!/usr/bin/env python3
"""
Run the email verification migration in Supabase.
The SQL is in database_email_verification.sql — run it in Supabase SQL Editor.
"""
import os
import sys

# Optional: run via Supabase client if SUPABASE_SERVICE_ROLE_KEY is set
def main():
    sql_path = os.path.join(os.path.dirname(__file__), "database_email_verification.sql")
    with open(sql_path) as f:
        sql = f.read()
    print("Run this SQL in Supabase Dashboard → SQL Editor → New query:")
    print("---")
    print(sql)
    print("---")
    print("Then save and run the query.")

if __name__ == "__main__":
    main()
