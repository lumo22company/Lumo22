"""
Fetch existing appointments by date for the available-slots API.
Used when "Group appointments together" is on to filter slots.
"""
from datetime import datetime, date, timedelta
from typing import List

from config import Config
from supabase import create_client


def _get_client():
    url = (Config.SUPABASE_URL or "").strip()
    key = (Config.SUPABASE_KEY or "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def get_appointment_starts_for_date(day: date) -> List[datetime]:
    """
    Return list of slot_start datetimes for appointments on the given date.
    Returns empty list if table missing or no rows (caller then shows all slots).
    """
    client = _get_client()
    if not client:
        return []
    try:
        start_str = day.isoformat() + "T00:00:00"
        next_day = (day + timedelta(days=1)).isoformat() + "T00:00:00"
        result = (
            client.table("appointments")
            .select("slot_start")
            .gte("slot_start", start_str)
            .lt("slot_start", next_day)
            .execute()
        )
        if not result.data:
            return []
        out = []
        for row in result.data:
            s = row.get("slot_start")
            if not s:
                continue
            if isinstance(s, str):
                # Parse ISO and drop tz for consistency with get_available_slots
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    out.append(dt.replace(tzinfo=None) if dt.tzinfo else dt)
                except ValueError:
                    pass
            else:
                out.append(s)
        return out
    except Exception as e:
        print(f"[appointments] get_appointment_starts_for_date error: {e}")
        return []
