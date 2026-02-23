"""
Calendly API provider for real-time availability.
Uses Personal Access Token: Calendly → Integrations → API & Webhooks → Generate token.
Event Type URI: from Calendly API /event_types or the share link (e.g. https://calendly.com/username/30min).
"""
import requests
from typing import List, Optional
from datetime import date, datetime


class CalendlyProvider:
    """Fetch available slots from Calendly API."""

    BASE = "https://api.calendly.com"

    def __init__(self, api_token: str, event_type_uri: str):
        self.api_token = (api_token or "").strip()
        self.event_type_uri = (event_type_uri or "").strip()
        if not self.api_token or not self.event_type_uri:
            raise ValueError("Calendly requires api_token and event_type_uri")

    @classmethod
    def from_setup(cls, setup: dict) -> "CalendlyProvider":
        token = (setup.get("calendly_api_token") or "").strip()
        uri = (setup.get("calendly_event_type_uri") or "").strip()
        if not token or not uri:
            raise ValueError("Calendly not configured")
        # Event type URI must be from Calendly API, e.g. https://api.calendly.com/event_types/XXX
        if "calendly.com" in uri and "api.calendly.com" not in uri:
            raise ValueError(
                "Use your Event Type URI from Calendly (Integrations → API & Webhooks → "
                "Event Types). Format: https://api.calendly.com/event_types/XXXXXXXX"
            )
        return cls(api_token=token, event_type_uri=uri)

    def get_available_slots(self, day: date) -> List[str]:
        """Fetch available times from Calendly for the given date."""
        start = datetime.combine(day, datetime.min.time()).strftime("%Y-%m-%dT00:00:00Z")
        end = datetime.combine(day, datetime.max.time()).strftime("%Y-%m-%dT23:59:59Z")
        url = f"{self.BASE}/event_type_available_times"
        params = {
            "event_type": self.event_type_uri,
            "start_time": start,
            "end_time": end,
        }
        headers = {"Authorization": f"Bearer {self.api_token}"}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[Calendly] API error: {e}")
            return []
        collection = data.get("collection") or []
        out = []
        for item in collection:
            start_time = item.get("start_time")
            if not start_time:
                continue
            try:
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                out.append(dt.strftime("%H:%M"))
            except Exception:
                pass
        return sorted(set(out))
