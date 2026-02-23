"""
Fetch existing appointments by date for the available-slots API.
Used when "Group appointments together" is on to filter slots.
Returns (start, end) ranges for duration-aware availability.
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple

from config import Config
from supabase import create_client


def _get_client():
    url = (Config.SUPABASE_URL or "").strip()
    key = (Config.SUPABASE_KEY or "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def _parse_dt(value) -> Optional[datetime]:
    """Parse slot_start or slot_end to naive datetime."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            return None
    if hasattr(value, "replace") and getattr(value, "tzinfo", None):
        return value.replace(tzinfo=None)
    return value


def get_appointments_for_date(day: date, default_duration_minutes: int = 30) -> List[Tuple[datetime, datetime]]:
    """
    Return list of (slot_start, slot_end) for appointments on the given date.
    Used for duration-aware tight scheduling and overlap exclusion.
    If slot_end is null, uses slot_start + default_duration_minutes.
    Returns empty list if table missing or no rows.
    """
    client = _get_client()
    if not client:
        return []
    try:
        # Use explicit UTC to match Supabase's default timezone
        start_str = day.isoformat() + "T00:00:00Z"
        next_day = (day + timedelta(days=1)).isoformat() + "T00:00:00Z"
        result = (
            client.table("appointments")
            .select("slot_start, slot_end")
            .gte("slot_start", start_str)
            .lt("slot_start", next_day)
            .execute()
        )
        if not result.data:
            return []
        out: List[Tuple[datetime, datetime]] = []
        default_delta = timedelta(minutes=default_duration_minutes)
        for row in result.data:
            start_dt = _parse_dt(row.get("slot_start"))
            if not start_dt or (getattr(start_dt, "date", None) and start_dt.date() != day):
                continue
            end_dt = _parse_dt(row.get("slot_end"))
            if end_dt is None or end_dt <= start_dt:
                end_dt = start_dt + default_delta
            out.append((start_dt, end_dt))
        return out
    except Exception as e:
        print(f"[appointments] get_appointments_for_date error: {e}")
        return []


def get_appointment_starts_for_date(day: date) -> List[datetime]:
    """
    Return list of slot_start datetimes for appointments on the given date.
    Kept for backward compatibility; prefer get_appointments_for_date for duration-aware logic.
    """
    ranges = get_appointments_for_date(day)
    return [start for start, _ in ranges]
