"""
Booking platform providers for real-time availability.
Each provider fetches slots from the business's actual booking system.
"""
from typing import List, Optional
from datetime import date

from .base import BaseBookingProvider
from .calendly import CalendlyProvider
from .vagaro import VagaroProvider
from .generic import GenericProvider

# Map platform ID to provider class
PROVIDERS = {
    "calendly": CalendlyProvider,
    "vagaro": VagaroProvider,
    "generic": GenericProvider,
}


def get_provider(platform: str, setup: dict) -> Optional[BaseBookingProvider]:
    """Return a provider instance for the given platform and setup config."""
    if not platform or platform not in PROVIDERS:
        return None
    cls = PROVIDERS[platform]
    try:
        return cls.from_setup(setup)
    except Exception:
        return None


def get_available_slots_for_setup(
    setup: dict, day: date
) -> List[str]:
    """
    Get available slot times (HH:MM) for a setup.
    Uses platform-specific provider if configured; else falls back to generic.
    """
    platform = (setup.get("booking_platform") or "").strip().lower()
    provider = get_provider(platform, setup)
    if provider:
        slots = provider.get_available_slots(day)
        if slots is not None:
            return slots
    # Fallback to generic
    generic = GenericProvider.from_setup(setup)
    return generic.get_available_slots(day)
