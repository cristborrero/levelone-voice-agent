"""
Cal.com API v2 client for ALEX booking integration.
- Auth: Bearer token (cal_live_xxx keys)
- Endpoints: /slots/available, /bookings
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SlotResult:
    start: str
    end: str


@dataclass
class BookingResult:
    uid: str
    start: str
    end: str
    meeting_url: str | None


class CalComClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.calcom_api_key
        self._event_type_id = int(settings.calcom_event_type_id)
        self._username = settings.calcom_username
        self._http = httpx.AsyncClient(
            base_url="https://api.cal.com/v2",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "cal-api-version": "2024-08-13",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_available_slots(
        self, date_from: datetime, date_to: datetime
    ) -> list[SlotResult]:
        resp = await self._http.get(
            "/slots/available",
            params={
                "eventTypeId": self._event_type_id,
                "startTime": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": date_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "username": self._username,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        slots: list[SlotResult] = []
        # v2 response: {"status":"success","data":{"slots":{"2024-01-15":[{"time":"...","endTime":"..."}]}}}
        slot_data = data.get("data", {}).get("slots", {})
        for day_slots in slot_data.values():
            for slot in day_slots:
                slots.append(SlotResult(
                    start=slot.get("time", slot.get("startTime", "")),
                    end=slot.get("endTime", ""),
                ))
        logger.info("calcom_slots_fetched", count=len(slots))
        return slots

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def book_slot(
        self,
        start: str,
        name: str,
        email: str,
        phone: str | None = None,
        notes: str | None = None,
    ) -> BookingResult:
        metadata: dict = {}
        if phone:
            metadata["phone"] = phone

        body = {
            "eventTypeId": self._event_type_id,
            "start": start,
            "attendee": {
                "name": name,
                "email": email,
                "timeZone": "Europe/London",
                "language": "en",
                "notes": notes or "",
            },
            "metadata": metadata,
        }

        resp = await self._http.post("/bookings", json=body)

        if resp.status_code == 422:
            # Slot may be taken — propagate for retry logic
            logger.warning("calcom_booking_422", body=resp.text)
            resp.raise_for_status()

        resp.raise_for_status()
        data = resp.json().get("data", resp.json())  # v2 wraps in data

        uid = data.get("uid", "")
        start_time = data.get("startTime", start)
        end_time = data.get("endTime", "")
        video_url = None
        for ref in data.get("references", []):
            if ref.get("type") in ("daily_video", "zoom_video", "google_meet_video"):
                video_url = ref.get("meetingUrl") or ref.get("meetingPassword")
                break

        logger.info("calcom_booking_created", uid=uid, start=start_time, name=name)
        return BookingResult(uid=uid, start=start_time, end=end_time, meeting_url=video_url)

    async def aclose(self) -> None:
        await self._http.aclose()
