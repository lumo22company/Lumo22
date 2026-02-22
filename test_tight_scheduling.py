#!/usr/bin/env python3
"""Test tight scheduling: availability logic and API payload handling."""
from datetime import datetime, timedelta
import sys

def test_filter_slots_tight_scheduling():
    from services.availability import filter_slots_tight_scheduling

    # Slots every hour 9–17
    base = datetime(2025, 2, 1, 9, 0)
    slot_times = [base + timedelta(hours=i) for i in range(9)]

    # Disabled → all slots returned
    out = filter_slots_tight_scheduling(slot_times, [base + timedelta(hours=12)], enabled=False, window_minutes=60)
    assert len(out) == 9, f"disabled: expected 9 slots, got {len(out)}"
    print("  OK disabled → all slots")

    # Enabled, no existing bookings → all slots
    out = filter_slots_tight_scheduling(slot_times, [], enabled=True, window_minutes=60)
    assert len(out) == 9, f"enabled no bookings: expected 9, got {len(out)}"
    print("  OK enabled, no bookings → all slots")

    # Enabled, one booking at 12:00 → only slots within ±60 min (11, 12, 13)
    existing = [base + timedelta(hours=3)]  # 12:00
    out = filter_slots_tight_scheduling(slot_times, existing, enabled=True, window_minutes=60)
    assert len(out) == 3, f"enabled 1 booking 60min: expected 3, got {len(out)}"
    assert out[0].hour == 11 and out[1].hour == 12 and out[2].hour == 13
    print("  OK enabled, 1 booking ±60min → 3 slots")

    # 30 min window → only 12:00 slot (and 11:30/12:30 if we had half-hour slots; with hourly we get 11,12,13 still since 11 is 60min away - actually 11 is 1hr from 12, so outside 30min. So we get 12 only? No: window is ±30min so 11:30-12:30. Our slots are 9,10,11,12,13... So 12 is in range. 11 is 60min before 12 so outside 30min. 13 is 60min after 12 so outside. So we get just [12]. Let me verify.
    out30 = filter_slots_tight_scheduling(slot_times, existing, enabled=True, window_minutes=30)
    assert len(out30) == 1 and out30[0].hour == 12, f"30min window: expected 1 slot (12), got {len(out30)}"
    print("  OK enabled, 1 booking ±30min → 1 slot")

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
