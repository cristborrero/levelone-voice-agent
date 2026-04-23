"""
CallOrchestrator — connects ALEX's conversations to Cal.com, HubSpot, and Resend.

FunctionTools registered (called by LLM mid-conversation):
  1. save_lead_info        — silently stores caller data in CallContext
  2. get_available_slots   — fetches real Cal.com slots
  3. book_discovery_call   — books slot + sends email + logs to HubSpot
  4. end_call_and_log      — creates HubSpot Call activity + sends follow-up email
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated

from livekit.agents import function_tool, RunContext

from app.agent.context import CallContext
from app.booking.calcom import CalComClient, BookingResult
from app.core.logging import get_logger
from app.crm.hubspot import HubSpotClient, ContactPayload
from app.email.resend_client import EmailClient

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: save_lead_info  (silent data accumulator)
# ---------------------------------------------------------------------------

@function_tool
async def save_lead_info(
    context: RunContext[CallContext],
    caller_name: Annotated[str | None, "Full name of the caller"] = None,
    business_name: Annotated[str | None, "Business or company name"] = None,
    need: Annotated[str | None, "What the caller needs or wants (service, problem)"] = None,
    budget: Annotated[str | None, "Approximate budget mentioned"] = None,
    timeline: Annotated[str | None, "When they want to start"] = None,
    email: Annotated[str | None, "Email address if provided"] = None,
) -> str:
    """
    Save information collected during the conversation into the call session.
    Call this SILENTLY every time the caller shares their name, business, need,
    budget, timeline, or email. Do NOT mention this action to the caller.
    """
    ctx = context.userdata
    if caller_name:
        ctx.contact_name = caller_name
    if business_name:
        ctx.business_name = business_name
    if need:
        ctx.need = need
    if budget:
        ctx.budget = budget
    if timeline:
        ctx.timeline = timeline
    if email:
        ctx.email = email

    logger.info(
        "lead_info_saved",
        name=ctx.contact_name,
        business=ctx.business_name,
        need=ctx.need,
        budget=ctx.budget,
    )
    return "ok"


# ---------------------------------------------------------------------------
# Tool 2: get_available_slots
# ---------------------------------------------------------------------------

@function_tool
async def get_available_slots(
    context: RunContext[CallContext],
    days_ahead: Annotated[int, "How many days ahead to look for slots (1-7)"] = 5,
) -> str:
    """
    Fetch the next available discovery call slots from Cal.com.
    Call this when the caller shows interest in booking a meeting.
    Returns a natural-language list of 3 time options to read to the caller.
    """
    cal = CalComClient()
    try:
        now = datetime.now(timezone.utc)
        slots = await cal.get_available_slots(
            date_from=now + timedelta(hours=2),
            date_to=now + timedelta(days=days_ahead),
        )
        if not slots:
            return (
                "I'm sorry, there are no available slots in the next few days. "
                "Could I take your email and have someone contact you directly to arrange a time?"
            )

        # Store first 3 slots in context for book_discovery_call
        ctx = context.userdata
        ctx.available_slots = slots[:3]

        # Format for natural speech
        readable = []
        for slot in slots[:3]:
            try:
                dt = datetime.fromisoformat(slot.start.replace("Z", "+00:00"))
                # e.g. "Thursday 24 April at 10:00 AM"
                readable.append(dt.strftime("%A %d %B at %-I:%M %p"))
            except Exception:
                readable.append(slot.start)

        if len(readable) == 1:
            options = readable[0]
        elif len(readable) == 2:
            options = f"{readable[0]} or {readable[1]}"
        else:
            options = f"{readable[0]}, {readable[1]}, or {readable[2]}"

        return (
            f"I have the following slots available: {options}. "
            "Which of those works best for you?"
        )

    except Exception as exc:
        logger.error("calcom_slots_error", error=str(exc))
        return (
            "I wasn't able to check availability right now. "
            "Could I take your details and we'll confirm a time by email?"
        )
    finally:
        await cal.aclose()


# ---------------------------------------------------------------------------
# Tool 3: book_discovery_call
# ---------------------------------------------------------------------------

@function_tool
async def book_discovery_call(
    context: RunContext[CallContext],
    slot_index: Annotated[int, "Which slot the caller chose: 0 = first, 1 = second, 2 = third"],
    caller_email: Annotated[str, "Caller's email address — MUST be collected before calling this"],
    caller_name: Annotated[str, "Caller's full name"],
) -> str:
    """
    Book the chosen discovery call slot on Cal.com, send a confirmation email,
    and create/update the lead in HubSpot.
    Only call this AFTER the caller has (1) chosen a slot AND (2) given their email.
    """
    ctx = context.userdata
    slots = getattr(ctx, "available_slots", [])

    if not slots or slot_index >= len(slots):
        return (
            "I'm having trouble confirming that slot. "
            "Let me take your email and a team member will confirm the booking manually."
        )

    chosen = slots[slot_index]
    cal = CalComClient()

    try:
        # 1. Create booking on Cal.com
        booking: BookingResult = await cal.book_slot(
            start=chosen.start,
            name=caller_name,
            email=caller_email,
            phone=ctx.caller_number,
            notes=(
                f"Inbound call via ALEX (voice agent).\n"
                f"Need: {ctx.need or 'not specified'}\n"
                f"Budget: {ctx.budget or 'not discussed'}\n"
                f"Timeline: {ctx.timeline or 'not discussed'}"
            ),
        )
        ctx.calcom_booking_uid = booking.uid
        ctx.email = caller_email
        ctx.contact_name = caller_name

        # 2. Email confirmation (background — don't block the voice response)
        asyncio.create_task(_send_confirmation_email(
            email=caller_email, name=caller_name, booking=booking
        ))

        # 3. HubSpot upsert (background)
        asyncio.create_task(_hubspot_booking_update(ctx, caller_name, caller_email, booking))

        # Format time for the caller
        try:
            dt = datetime.fromisoformat(booking.start.replace("Z", "+00:00"))
            human_time = dt.strftime("%A %d %B at %-I:%M %p")
        except Exception:
            human_time = booking.start

        logger.info("booking_completed", uid=booking.uid, caller=caller_name)
        return (
            f"Brilliant! Your discovery call is confirmed for {human_time}. "
            f"A confirmation email is on its way to {caller_email}. "
            f"{'A video call link is included.' if booking.meeting_url else ''} "
            "We're really looking forward to speaking with you!"
        )

    except Exception as exc:
        logger.error("booking_error", error=str(exc))
        return (
            f"I'm sorry, there was a problem confirming the booking. "
            f"I'll make sure a team member follows up with you at {caller_email} shortly."
        )
    finally:
        await cal.aclose()


async def _send_confirmation_email(email: str, name: str, booking: BookingResult) -> None:
    try:
        ec = EmailClient()
        await ec.send_booking_confirmation(
            to=email,
            name=name,
            meeting_start=booking.start,
            meeting_url=booking.meeting_url,
        )
    except Exception as exc:
        logger.error("email_confirmation_error", error=str(exc))


async def _hubspot_booking_update(
    ctx: CallContext, name: str, email: str, booking: BookingResult
) -> None:
    """Background: upsert contact, add booking note."""
    hs = HubSpotClient()
    try:
        first, *rest = name.split(" ", 1)
        last = rest[0] if rest else ""

        contact_id = await hs.upsert_contact(ContactPayload(
            phone=ctx.caller_number,
            firstname=first,
            lastname=last,
            email=email,
            company=ctx.business_name,
            hs_lead_status="IN_PROGRESS",
        ))
        ctx.hubspot_contact_id = contact_id

        try:
            dt = datetime.fromisoformat(booking.start.replace("Z", "+00:00"))
            human_time = dt.strftime("%A %d %B %Y at %H:%M UTC")
        except Exception:
            human_time = booking.start

        await hs.add_note(
            contact_id=contact_id,
            body=(
                f"✅ Discovery call booked via ALEX (voice agent)\n"
                f"📅 Time: {human_time}\n"
                f"🔗 Meeting: {booking.meeting_url or 'TBC'}\n"
                f"📋 Cal.com UID: {booking.uid}\n\n"
                f"Lead information captured:\n"
                f"  💬 Need: {ctx.need or '—'}\n"
                f"  💰 Budget: {ctx.budget or '—'}\n"
                f"  🗓️ Timeline: {ctx.timeline or '—'}\n"
                f"  🏢 Business: {ctx.business_name or '—'}"
            ),
        )

    except Exception as exc:
        logger.error("hubspot_booking_update_error", error=str(exc))
    finally:
        await hs.aclose()


# ---------------------------------------------------------------------------
# Tool 4: end_call_and_log
# ---------------------------------------------------------------------------

@function_tool
async def end_call_and_log(
    context: RunContext[CallContext],
    outcome: Annotated[
        str,
        "One of: meeting_booked, follow_up, not_qualified, info_only"
    ],
    summary: Annotated[
        str,
        "2-3 sentence summary of the call for the CRM note"
    ],
) -> str:
    """
    Log the call outcome to HubSpot (contact + formal Call activity).
    Send a follow-up email if outcome is follow_up.
    ALWAYS call this before saying goodbye — every single call.
    """
    ctx = context.userdata
    hs = HubSpotClient()

    try:
        # Build contact
        name = ctx.contact_name or "Unknown Caller"
        first, *rest = name.split(" ", 1)
        last = rest[0] if rest else ""

        hs_status = {
            "meeting_booked": "IN_PROGRESS",
            "follow_up": "OPEN",
            "not_qualified": "UNQUALIFIED",
            "info_only": "OPEN",
        }.get(outcome, "OPEN")

        contact_id = ctx.hubspot_contact_id or await hs.upsert_contact(ContactPayload(
            phone=ctx.caller_number,
            firstname=first,
            lastname=last,
            email=ctx.email,
            company=ctx.business_name,
            hs_lead_status=hs_status,
        ))
        ctx.hubspot_contact_id = contact_id

        # Update lead status if contact already existed
        if ctx.hubspot_contact_id:
            await hs._http.patch(
                f"/crm/v3/objects/contacts/{contact_id}",
                json={"properties": {"hs_lead_status": hs_status}},
            )

        # Formal Call activity
        duration = int((datetime.utcnow() - ctx.started_at).total_seconds())
        await hs.log_call_activity(
            contact_id=contact_id,
            call_title=f"Inbound Call — {outcome.replace('_', ' ').title()} — ALEX",
            duration_seconds=duration,
            outcome=outcome,
            body=(
                f"📝 {summary}\n\n"
                f"💬 Need: {ctx.need or '—'}\n"
                f"💰 Budget: {ctx.budget or '—'}\n"
                f"🗓️ Timeline: {ctx.timeline or '—'}\n"
                f"🏢 Business: {ctx.business_name or '—'}\n"
                f"📅 Meeting booked: {'✅ ' + ctx.calcom_booking_uid if ctx.calcom_booking_uid else '❌ No'}"
            ),
        )

        # Follow-up email (background)
        if ctx.email and ctx.contact_name and outcome == "follow_up":
            asyncio.create_task(_send_followup_email(
                email=ctx.email, name=ctx.contact_name, summary=summary
            ))

        logger.info("call_logged", outcome=outcome, contact_id=contact_id, duration=duration)
        return "ok"

    except Exception as exc:
        logger.error("end_call_log_error", error=str(exc))
        return "ok"  # Always return ok — don't block the agent goodbye
    finally:
        await hs.aclose()


async def _send_followup_email(email: str, name: str, summary: str) -> None:
    try:
        ec = EmailClient()
        await ec.send_followup(to=email, name=name, summary=summary)
    except Exception as exc:
        logger.error("email_followup_error", error=str(exc))


# ---------------------------------------------------------------------------
# Exports — register in AgentSession
# ---------------------------------------------------------------------------

ALEX_TOOLS = [
    save_lead_info,
    get_available_slots,
    book_discovery_call,
    end_call_and_log,
]
