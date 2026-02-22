"""
Booking availability for Digital Front Desk.

- Generates available slot times for a day from working hours and slot length.
- Optional "tight scheduling": only show slots within a configurable time window
  of existing same-day bookings. If no bookings that day, show all slots.
- Duration-aware: uses existing booking (start, end) and new appointment duration
  to exclude overlaps and consider full appointment ranges when clustering.
"""
from datetime import datetime, timedelta, time
from typing import List, Tuple, Union


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
    existing_bookings: Union[List[datetime], List[Tuple[datetime, datetime]]],
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
    are returned (duration-aware: considers booking end times too).
    Overlapping slots are always excluded.
    If tight_schedule is True but there are no bookings, all slots are returned.

    Args:
        date: The day (date or datetime; time part ignored).
        existing_bookings: List of (start, end) tuples, or list of start datetimes
            (end inferred as start + slot_minutes for backward compat).
        slot_minutes: Length of each slot / new appointment in minutes (default 30).
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

    # Normalize existing_bookings to (start, end) tuples
    same_day_ranges: List[Tuple[datetime, datetime]] = []
    default_delta = timedelta(minutes=slot_minutes)
    for item in existing_bookings:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                start_dt = item[0]
                end_dt = item[1]
            else:
                start_dt = item
                end_dt = start_dt + default_delta
            start_dt = start_dt.replace(tzinfo=None) if getattr(start_dt, "tzinfo", None) else start_dt
            if getattr(end_dt, "tzinfo", None):
                end_dt = end_dt.replace(tzinfo=None)
            if getattr(start_dt, "date", None) and start_dt.date() == day:
                if end_dt is None or end_dt <= start_dt:
                    end_dt = start_dt + default_delta
                same_day_ranges.append((start_dt, end_dt))
        except Exception:
            pass

    # Apply overlap exclusion (always) and tight scheduling filter when enabled
    return filter_slots_tight_scheduling(
        slot_times,
        same_day_ranges,
        slot_minutes=slot_minutes,
        enabled=tight_schedule,
        window_minutes=max(5, gap_minutes),
    )


def _ranges_overlap(
    a_start: datetime, a_end: datetime,
    b_start: datetime, b_end: datetime,
) -> bool:
    """True if [a_start, a_end) overlaps [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def _min_distance_between_ranges(
    a_start: datetime, a_end: datetime,
    b_start: datetime, b_end: datetime,
) -> float:
    """Min distance in seconds between two ranges. 0 if they overlap."""
    if _ranges_overlap(a_start, a_end, b_start, b_end):
        return 0.0
    if a_end <= b_start:
        return (b_start - a_end).total_seconds()
    return (a_start - b_end).total_seconds()


def filter_slots_by_clustering(
    slot_times: List[datetime],
    existing_bookings_same_day: List[Tuple[datetime, datetime]],
    slot_minutes: int,
    window_minutes: float,
) -> List[datetime]:
    """
    Return slots that are within window_minutes of existing bookings.
    Excludes slots that would overlap existing bookings.
    Duration-aware: uses (start, end) of existing bookings and slot_minutes for new appt.
    """
    if not existing_bookings_same_day:
        return list(slot_times)
    window_seconds = window_minutes * 60
    slot_delta = timedelta(minutes=slot_minutes)
    result = []
    for slot in slot_times:
        new_start = slot
        new_end = slot + slot_delta
        # Exclude overlapping slots
        overlaps = any(
            _ranges_overlap(new_start, new_end, ex_start, ex_end)
            for ex_start, ex_end in existing_bookings_same_day
        )
        if overlaps:
            continue
        # Include if within window of any existing booking
        for ex_start, ex_end in existing_bookings_same_day:
            dist = _min_distance_between_ranges(new_start, new_end, ex_start, ex_end)
            if dist <= window_seconds:
                result.append(slot)
                break
    return result


def filter_slots_tight_scheduling(
    slot_times: List[datetime],
    existing_bookings_same_day: List[Tuple[datetime, datetime]],
    slot_minutes: int = 30,
    enabled: bool = False,
    window_minutes: int = 60,
) -> List[datetime]:
    """
    Apply tight scheduling: exclude overlapping slots, and when enabled,
    only show slots within window_minutes of existing same-day bookings.

    - Overlap exclusion: always applied (no double-booking).
    - If enabled is False: return all non-overlapping slot_times.
    - If enabled is True and no existing bookings: return all slot_times.
    - If enabled is True and there are existing bookings: return only slots
      within window_minutes of any existing booking (considering full ranges).
    """
    # Always exclude overlapping slots
    slot_delta = timedelta(minutes=slot_minutes)
    non_overlapping = []
    for slot in slot_times:
        new_start = slot
        new_end = slot + slot_delta
        overlaps = any(
            _ranges_overlap(new_start, new_end, ex_start, ex_end)
            for ex_start, ex_end in existing_bookings_same_day
        )
        if not overlaps:
            non_overlapping.append(slot)

    if not enabled or not existing_bookings_same_day:
        return non_overlapping
    return filter_slots_by_clustering(
        non_overlapping,
        existing_bookings_same_day,
        slot_minutes=slot_minutes,
        window_minutes=float(window_minutes),
    )
