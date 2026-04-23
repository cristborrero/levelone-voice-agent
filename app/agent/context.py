from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from app.core.enums import CallStage, Intent, LeadScore

if TYPE_CHECKING:
    from app.booking.calcom import SlotResult


@dataclass
class CallContext:
    call_id: str
    caller_number: str
    livekit_room: str
    started_at: datetime = field(default_factory=datetime.utcnow)

    stage: CallStage = CallStage.GREETING
    intent: Intent | None = None
    lead_score: LeadScore | None = None

    # Collected lead data
    contact_name: str | None = None
    business_name: str | None = None
    email: str | None = None
    budget: str | None = None
    timeline: str | None = None
    need: str | None = None

    # External IDs
    hubspot_contact_id: str | None = None
    hubspot_deal_id: str | None = None
    calcom_booking_uid: str | None = None

    # Conversation history (for LLM context)
    messages: list[dict[str, str]] = field(default_factory=list)

    # Temporary slot storage between get_available_slots → book_discovery_call
    available_slots: list = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def advance_stage(self, next_stage: CallStage) -> None:
        self.stage = next_stage
