#!/usr/bin/env python3
"""Test tight scheduling: availability logic and API payload handling."""
from datetime import datetime, timedelta
import sys

def test_filter_slots_tight_scheduling():
    from services.availability import filter_slots_tight_scheduling

    # Slots every hour 9–17 (slot_minutes=60)
    base = datetime(2025, 2, 1, 9, 0)
    slot_times = [base + timedelta(hours=i) for i in range(9)]
    slot_minutes = 60
    # Existing booking 12:00–13:00
    existing = [(base + timedelta(hours=3), base + timedelta(hours=4))]

    # Disabled → all non-overlapping slots (12:00 overlaps 12–13, so 8 slots)
    out = filter_slots_tight_scheduling(
        slot_times, existing, slot_minutes=slot_minutes, enabled=False, window_minutes=60
    )
    assert len(out) == 8, f"disabled: expected 8 slots (12 excluded), got {len(out)}"
    assert 12 not in [s.hour for s in out]
    print("  OK disabled → 8 slots (12 excluded by overlap)")

    # Enabled, no existing bookings → all slots
    out = filter_slots_tight_scheduling(
        slot_times, [], slot_minutes=slot_minutes, enabled=True, window_minutes=60
    )
    assert len(out) == 9, f"enabled no bookings: expected 9, got {len(out)}"
    print("  OK enabled, no bookings → all slots")

    # Enabled, one booking 12:00–13:00 → slots within 60min of range: 10–11 (dist 60m), 11–12 (0), 13–14 (0), 14–15 (60m). 12 excluded overlap.
    out = filter_slots_tight_scheduling(
        slot_times, existing, slot_minutes=slot_minutes, enabled=True, window_minutes=60
    )
    assert len(out) == 4 and set(s.hour for s in out) == {10, 11, 13, 14}, (
        f"enabled 1 booking 60min: expected [10,11,13,14], got {[s.hour for s in out]}"
    )
    print("  OK enabled, 1 booking ±60min → 4 slots (10, 11, 13, 14; 12 excluded overlap)")

    # 30 min window → 11 (11–12) touches 12–13 at 12, dist=0. 13 (13–14) touches at 13, dist=0. Both in.
    out30 = filter_slots_tight_scheduling(
        slot_times, existing, slot_minutes=slot_minutes, enabled=True, window_minutes=30
    )
    assert len(out30) == 2 and out30[0].hour == 11 and out30[1].hour == 13, (
        f"30min: expected [11,13], got {[s.hour for s in out30]}"
    )
    print("  OK enabled, 1 booking ±30min → 2 slots (11, 13)")

    # Duration-aware overlap: 90-min slots, booking 12:00–13:00. 11:00 slot = 11:00–12:30, overlaps.
    slot_times_90 = [base + timedelta(hours=i) for i in range(9)]
    out90 = filter_slots_tight_scheduling(
        slot_times_90, existing, slot_minutes=90, enabled=False, window_minutes=60
    )
    # 11–12:30 overlaps 12–13; 12–13:30 overlaps. So 11 and 12 excluded. 9,10,13,14,15,16,17 = 7
    assert 11 not in [s.hour for s in out90], "11:00 90min should be excluded (overlaps 12–13)"
    assert 12 not in [s.hour for s in out90], "12:00 90min should be excluded (overlaps 12–13)"
    print("  OK duration-aware: 90min slots exclude overlapping 11 and 12")

    print("availability.filter_slots_tight_scheduling: all checks passed")
    return True


def test_api_payload_parsing():
    """Simulate API parsing of tight_scheduling_enabled and minimum_gap_between_appointments."""
    def parse(data):
        tight_scheduling_enabled = bool(data.get("tight_scheduling_enabled"))
        raw_gap = data.get("minimum_gap_between_appointments")
        minimum_gap_between_appointments = 60
        if raw_gap is not None:
            try:
                minimum_gap_between_appointments = max(15, min(480, int(raw_gap)))
            except (TypeError, ValueError):
                pass
        return tight_scheduling_enabled, minimum_gap_between_appointments

    off, gap = parse({})
    assert off is False and gap == 60
    print("  OK missing → off, 60")

    off, gap = parse({"tight_scheduling_enabled": True, "minimum_gap_between_appointments": 45})
    assert off is True and gap == 45
    print("  OK on + 45 → on, 45")

    off, gap = parse({"tight_scheduling_enabled": 1, "minimum_gap_between_appointments": "90"})
    assert off is True and gap == 90
    print("  OK 1 + '90' → on, 90")

    off, gap = parse({"minimum_gap_between_appointments": 10})
    assert gap == 15  # clamped to 15
    print("  OK gap 10 → clamped 15")

    off, gap = parse({"minimum_gap_between_appointments": 999})
    assert gap == 480  # clamped to 480
    print("  OK gap 999 → clamped 480")

    print("API payload parsing: all checks passed")
    return True


if __name__ == "__main__":
    ok = True
    print("Testing tight scheduling...")
    try:
        test_filter_slots_tight_scheduling()
    except Exception as e:
        print(f"  FAIL: {e}")
        ok = False
    try:
        test_api_payload_parsing()
    except Exception as e:
        print(f"  FAIL: {e}")
        ok = False
    sys.exit(0 if ok else 1)
