"""
HubSpot CRM client for ALEX.

Scopes activos (Private App pat-eu1-xxx):
  ✅ crm.objects.contacts.read/write
  ✅ crm.objects.notes.read/write      (via crm.objects.contacts scope)
  ✅ crm.objects.calls.read/write      (idem)
  ✅ crm.objects.owners.read
  ❌ crm.objects.deals.write           (no disponible en plan — skip gracefully)

Operations:
  upsert_contact      — create or update by phone
  add_note            — log a text note on a contact
  log_call_activity   — create a formal Call engagement
  get_owners          — list CRM owners
  aclose              — cleanup
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE = "https://api.hubapi.com"


def _epoch_ms() -> str:
    """Current time as epoch milliseconds string (required by HubSpot hs_timestamp)."""
    return str(int(datetime.now(timezone.utc).timestamp() * 1000))


@dataclass
class ContactPayload:
    phone: str
    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    company: str | None = None
    hs_lead_status: str = "NEW"


class HubSpotClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.hubspot_access_token
        self._owner_id = settings.hubspot_owner_id
        self._http = httpx.AsyncClient(
            base_url=_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=12.0,
        )

    # -------------------------------------------------------------------------
    # Contact
    # -------------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def upsert_contact(self, payload: ContactPayload) -> str:
        """Create or update a contact by phone number. Returns contact ID."""
        props: dict = {k: v for k, v in {
            "phone": payload.phone,
            "firstname": payload.firstname,
            "lastname": payload.lastname,
            "email": payload.email,
            "company": payload.company,
            "hs_lead_status": payload.hs_lead_status,
        }.items() if v is not None}

        if self._owner_id:
            props["hubspot_owner_id"] = self._owner_id

        # Search existing contact by phone
        search = await self._http.post(
            "/crm/v3/objects/contacts/search",
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "phone",
                        "operator": "EQ",
                        "value": payload.phone,
                    }]
                }],
                "limit": 1,
                "properties": ["id", "firstname", "lastname", "email"],
            },
        )
        search.raise_for_status()
        results = search.json().get("results", [])

        if results:
            contact_id = results[0]["id"]
            await self._http.patch(
                f"/crm/v3/objects/contacts/{contact_id}",
                json={"properties": props},
            )
            logger.info("contact_updated", contact_id=contact_id)
            return contact_id

        resp = await self._http.post(
            "/crm/v3/objects/contacts",
            json={"properties": props},
        )
        resp.raise_for_status()
        contact_id = resp.json()["id"]
        logger.info("contact_created", contact_id=contact_id)
        return contact_id

    # -------------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def add_note(self, contact_id: str, body: str) -> str:
        """Add a text note associated to a contact. Returns note ID."""
        resp = await self._http.post(
            "/crm/v3/objects/notes",
            json={"properties": {
                "hs_note_body": body,
                "hs_timestamp": _epoch_ms(),
            }},
        )
        resp.raise_for_status()
        note_id = resp.json()["id"]

        # Associate note → contact (type 202)
        await self._http.put(
            f"/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/202"
        )
        logger.info("note_added", note_id=note_id, contact_id=contact_id)
        return note_id

    # -------------------------------------------------------------------------
    # Call Activity
    # -------------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def log_call_activity(
        self,
        contact_id: str,
        call_title: str,
        duration_seconds: int,
        outcome: str,
        body: str,
    ) -> str:
        """
        Create a formal Call engagement on HubSpot and associate to contact.
        Requires crm.objects.calls scope (confirmed working with current token).
        Returns call engagement ID.
        """
        hs_outcome = {
            "meeting_booked": "CONNECTED",
            "follow_up": "CONNECTED",
            "not_qualified": "CONNECTED",
            "info_only": "CONNECTED",
        }.get(outcome, "CONNECTED")

        resp = await self._http.post(
            "/crm/v3/objects/calls",
            json={"properties": {
                "hs_call_title": call_title,
                "hs_call_duration": duration_seconds * 1000,  # HubSpot expects ms
                "hs_call_status": "COMPLETED",
                "hs_call_disposition": hs_outcome,
                "hs_call_body": body,
                "hs_timestamp": _epoch_ms(),
                **({"hubspot_owner_id": self._owner_id} if self._owner_id else {}),
            }},
        )
        resp.raise_for_status()
        call_id = resp.json()["id"]

        # Associate call → contact (type 194)
        await self._http.put(
            f"/crm/v3/objects/calls/{call_id}/associations/contacts/{contact_id}/194"
        )
        logger.info("call_activity_logged", call_id=call_id, contact_id=contact_id, outcome=outcome)
        return call_id

    # -------------------------------------------------------------------------
    # Owners (read-only helper)
    # -------------------------------------------------------------------------

    async def get_owners(self) -> list[dict]:
        resp = await self._http.get("/crm/v3/owners")
        resp.raise_for_status()
        return resp.json().get("results", [])

    # -------------------------------------------------------------------------

    async def aclose(self) -> None:
        await self._http.aclose()
