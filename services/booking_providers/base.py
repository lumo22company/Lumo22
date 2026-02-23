"""Base class for booking platform providers."""
from abc import ABC, abstractmethod
from typing import List
from datetime import date


class BaseBookingProvider(ABC):
    """Abstract base for fetching availability from a booking platform."""

    @classmethod
    @abstractmethod
    def from_setup(cls, setup: dict) -> "BaseBookingProvider":
        """Create provider from front_desk_setup row. Raises if config invalid."""
        pass

    @abstractmethod
    def get_available_slots(self, day: date) -> List[str]:
        """Return list of slot times as HH:MM strings for the given date."""
        pass
