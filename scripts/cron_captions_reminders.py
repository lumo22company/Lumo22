#!/usr/bin/env python3
"""
Railway cron: hit /api/captions-send-reminders daily.
Run as a separate Railway service with Cron Schedule: 0 9 * * * (9am UTC).
Set BASE_URL and CRON_SECRET in this service's variables (or inherit from project).
"""
import os
import sys
import urllib.request
import urllib.error

BASE_URL = (os.environ.get("BASE_URL") or "https://lumo-22-production.up.railway.app").rstrip("/")
CRON_SECRET = (os.environ.get("CRON_SECRET") or "").strip()
URL = f"{BASE_URL}/api/captions-send-reminders?secret={CRON_SECRET}"

if not CRON_SECRET:
    print("CRON_SECRET not set", file=sys.stderr)
    sys.exit(1)

try:
    req = urllib.request.Request(URL, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode()
        print(f"status={resp.status} body={body[:500]}")
        sys.exit(0 if 200 <= resp.status < 300 else 1)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
