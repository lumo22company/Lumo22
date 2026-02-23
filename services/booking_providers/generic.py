"""Generic provider: uses work hours + appointments table (no external API)."""
from typing import List
from datetime import date, datetime

from .base import BaseBookingProvider


class GenericProvider(BaseBookingProvider):
    """Generate slots from work_start/work_end and exclude appointments table."""

    @classmethod
    def from_setup(cls, setup: dict) -> "GenericProvider":
        return cls(setup=setup)

    def __init__(self, setup: dict):
        self.setup = setup or {}

    def get_available_slots(self, day: date) -> List[str]:
        from services.availability import get_available_slots
        from services.appointments_service import get_appointments_for_date

        slot_minutes = max(
            15, min(120, self.setup.get("appointment_duration_minutes") or 60)
        )
        work_start = (self.setup.get("work_start") or "").strip() or "09:00"
        work_end = (self.setup.get("work_end") or "").strip() or "17:00"
        tight_schedule = bool(self.setup.get("tight_scheduling_enabled"))
        gap_minutes = max(
            5, min(480, self.setup.get("minimum_gap_between_appointments") or 60)
        )
        existing = get_appointments_for_date(day, default_duration_minutes=slot_minutes)
        slots = get_available_slots(
            day.isoformat(),
            existing,
            slot_minutes=slot_minutes,
            work_start=work_start,
            work_end=work_end,
            tight_schedule=tight_schedule,
            gap_minutes=gap_minutes,
        )
        return [s.strftime("%H:%M") for s in slots]
