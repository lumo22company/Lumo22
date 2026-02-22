"""
Booking availability for Digital Front Desk.

- Generates available slot times for a day from working hours and slot length.
- Optional "tight scheduling": only show slots within a configurable time window
  of existing same-day bookings. If no bookings that day, show all slots.
"""
from datetime import datetime, timedelta, time
from typing import List, Union


def _parse_work_time(value: Union[str, tuple, None], default_hour: int, default_minute: int) -> time:
    """Convert work_start/work_end to time. Accepts 'HH:MM', (hour, minute), or None."""
    if value is None:
        return time(default_hour, default_minute)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return time(int(value[0]), int(value[1]))
    if isinstance(value, str):
        parts = value.strip().split(":")
        h = int(parts[0]) if parts else default_hour
        m = int(parts[1]) if len(parts) > 1 else default_minute
        return time(h, m)
    return time(default_hour, default_minute)


def get_available_slots(
    date: Union[datetime, str],
    existing_booking_times: List[datetime],
    slot_minutes: int = 30,
    work_start: Union[str, tuple, None] = None,
    work_end: Union[str, tuple, None] = None,
    tight_schedule: bool = False,
    gap_minutes: int = 60,
) -> List[datetime]:
    """
    Return available appointment slot start times for the given day.

    Slots are generated from work_start to work_end (default 09:00–17:00),
    every slot_minutes. If tight_schedule is True and there are existing
    bookings that day, only slots within gap_minutes of an existing booking
    are returned. If tight_schedule is True but there are no bookings,
    all slots are returned (no blocking).

    Args:
        date: The day (date or datetime; time part ignored).
        existing_booking_times: Start times of existing bookings on that day.
        slot_minutes: Length of each slot in minutes (default 30).
        work_start: Start of working day, e.g. "09:00" or (9, 0). Default 09:00.
        work_end: End of working day, e.g. "17:00" or (17, 0). Default 17:00.
        tight_schedule: If True, filter to slots near existing bookings when any exist.
        gap_minutes: Max minutes before/after an existing booking to include a slot (default 60).

    Returns:
        List of slot start datetimes (timezone-naive, date + time).
    """
    if isinstance(date, str):
        date = datetime.strptime(date.strip()[:10], "%Y-%m-%d")
    day = date.date() if hasattr(date, "date") else date
    start_t = _parse_work_time(work_start, 9, 0)
    end_t = _parse_work_time(work_end, 17, 0)
    slot_delta = timedelta(minutes=max(1, slot_minutes))

    # Build all slot start times for the day
    slot_times = []
    current = datetime.combine(day, start_t)
    end_dt = datetime.combine(day, end_t)
    while current < end_dt:
        slot_times.append(current)
        current += slot_delta

    # Restrict to existing bookings on this day (ignore timezone for date comparison)
    same_day = []
    for t in existing_booking_times:
        try:
            dt = t.replace(tzinfo=None) if hasattr(t, "replace") and getattr(t, "tzinfo", None) else t
            if getattr(dt, "date", None) and dt.date() == day:
                same_day.append(dt)
        except Exception:
            pass

    # Apply tight scheduling filter when enabled
    return filter_slots_tight_scheduling(
        slot_times,
        same_day,
        enabled=tight_schedule,
        window_minutes=max(5, gap_minutes),
    )


def filter_slots_by_clustering(
    slot_times: List[datetime],
    existing_booking_times_same_day: List[datetime],
    window_hours: float = 1.0,
) -> List[datetime]:
    """
    Return slots to show for a given day.

    - If the day has NO existing bookings: return all slot_times.
    - If the day HAS one or more bookings: return only slots within ±window_hours
      of any existing booking on that same day.

    Call this before rendering available times (e.g. slot picker from Calendly).
    """
    if not existing_booking_times_same_day:
        return list(slot_times)
    window = timedelta(hours=window_hours)
    result = []
    for slot in slot_times:
        for existing in existing_booking_times_same_day:
            if abs((slot - existing).total_seconds()) <= window.total_seconds():
                result.append(slot)
                break
    return result


def filter_slots_tight_scheduling(
    slot_times: List[datetime],
    existing_booking_times_same_day: List[datetime],
    enabled: bool,
    window_minutes: int = 60,
) -> List[datetime]:
    """
    Apply optional tight scheduling: only show slots within window_minutes of
    existing same-day bookings when enabled; otherwise return all slots.

    - If enabled is False: return all slot_times (no filtering).
    - If enabled is True and there are no existing bookings that day: return all slot_times.
    - If enabled is True and there are existing bookings: return only slots within
      ±window_minutes of any existing booking (same semantics as filter_slots_by_clustering).

    window_minutes: configurable gap (default 60). Used as the ± window in minutes.
    """
    if not enabled:
        return list(slot_times)
    window_hours = max(0, window_minutes) / 60.0
    return filter_slots_by_clustering(
        slot_times,
        existing_booking_times_same_day,
        window_hours=window_hours,
    )
