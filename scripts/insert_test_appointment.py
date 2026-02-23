#!/usr/bin/env python3
"""
Insert one test appointment so /book-demo with "Group appointments together" shows filtered slots.
Usage: python3 scripts/insert_test_appointment.py [YYYY-MM-DD]
Default: tomorrow at 14:00 (2pm) for 60 min. Requires SUPABASE_URL and SUPABASE_KEY in .env.
"""
import os
import sys
from datetime import datetime, timedelta, time
from pathlib import Path

# Load .env from project root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / ".env")

def main():
    url = (os.getenv("SUPABASE_URL") or "").strip()
    # Use service role key to bypass RLS (appointments table denies anon/authenticated)
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

    slot_start = datetime.combine(day, time(14, 0))  # 2pm
    slot_end = slot_start + timedelta(minutes=60)    # 60 min (2pm-3pm)
    from supabase import create_client
    client = create_client(url, key)
    row = {
        "slot_start": slot_start.isoformat(),
        "slot_end": slot_end.isoformat(),
    }
    result = client.table("appointments").insert(row).execute()
    if result.data:
        print(f"Inserted test appointment: {day} at 14:00 (2pm-3pm, 60 min)")
        print("Go to /book-demo, choose that date, turn on 'Group appointments together' to see only nearby slots.")
    else:
        print("Insert failed (table may not exist — run database_appointments.sql first)")
        sys.exit(1)

if __name__ == "__main__":
    main()
