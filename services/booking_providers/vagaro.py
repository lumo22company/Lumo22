"""
Vagaro API provider for real-time availability.
Requires: access token, business ID, service ID, region (us, uk, etc.).
Docs: https://docs.vagaro.com/public/reference/search-availability
"""
import requests
from typing import List
from datetime import date


class VagaroProvider:
    """Fetch available slots from Vagaro API."""

    BASE = "https://api.vagaro.com"

    def __init__(self, access_token: str, business_id: str, service_id: str, region: str = "us"):
        self.access_token = (access_token or "").strip()
        self.business_id = (business_id or "").strip()
        self.service_id = (service_id or "").strip()
        self.region = (region or "us").strip().lower() or "us"
        if not self.access_token or not self.business_id or not self.service_id:
            raise ValueError("Vagaro requires access_token, business_id, and service_id")

    @classmethod
    def from_setup(cls, setup: dict) -> "VagaroProvider":
        token = (setup.get("vagaro_access_token") or "").strip()
        biz = (setup.get("vagaro_business_id") or "").strip()
        svc = (setup.get("vagaro_service_id") or "").strip()
        region = (setup.get("vagaro_region") or "us").strip().lower()
        if not token or not biz or not svc:
            raise ValueError("Vagaro not configured")
        return cls(access_token=token, business_id=biz, service_id=svc, region=region)

    def get_available_slots(self, day: date) -> List[str]:
        """Fetch available times from Vagaro for the given date."""
        url = f"{self.BASE}/{self.region}/api/v2/appointments/availability"
        headers = {"accessToken": self.access_token, "Content-Type": "application/json"}
        payload = {
            "businessId": self.business_id,
            "appointmentDate": day.isoformat(),
            "bookingItems": [{"serviceId": self.service_id}],
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[Vagaro] API error: {e}")
            return []
        items = data.get("data") or []
        slots = set()
        for item in items:
            for t in item.get("timeSlot") or []:
                if t and isinstance(t, str):
                    slots.add(t)
        return sorted(slots)
