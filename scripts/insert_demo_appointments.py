#!/usr/bin/env python3
"""
Insert one demo appointment (2pm–3pm tomorrow) for /book-demo testing.
The 14:00 slot will be excluded when picking times.
Usage: python3 scripts/insert_demo_appointments.py [YYYY-MM-DD]
Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) in .env
"""
import os
import sys
from datetime import datetime, timedelta, time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / ".env")

def main():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) must be set in .env")
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

    from supabase import create_client
    client = create_client(url, key)

    # Delete existing demo appointments (optional - keeps table clean)
    try:
        start_str = day.isoformat() + "T00:00:00"
        next_str = (day + timedelta(days=1)).isoformat() + "T00:00:00"
        client.table("appointments").delete().gte("slot_start", start_str).lt("slot_start", next_str).execute()
    except Exception:
        pass

    # Insert one appointment: 2pm–3pm (explicit UTC for Supabase)
    rows = [
        {"slot_start": day.isoformat() + "T14:00:00Z", "slot_end": day.isoformat() + "T15:00:00Z"},
    ]
    try:
        result = client.table("appointments").insert(rows).execute()
        if result.data:
            print(f"Inserted 1 appointment for {day}: 14:00–15:00 (2pm–3pm)")
            print("Go to /book-demo and pick that date — 14:00 should be missing.")
        else:
            print("Insert failed (run database_appointments.sql in Supabase first)")
            sys.exit(1)
    except Exception as e:
        if "row-level security" in str(e).lower() or "42501" in str(e):
            print("ERROR: RLS blocked insert. Add SUPABASE_SERVICE_ROLE_KEY to .env")
            print("(Supabase → Settings → API → service_role secret)")
            print("\nOr run the SQL in INSERT_TEST_APPOINTMENT_NOW.md in Supabase SQL Editor.")
        else:
            print(f"Insert failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
