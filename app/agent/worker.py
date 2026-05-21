"""
ALEX Agent Worker — LiveKit entrypoint.

Connects: OpenAI LLM + Cartesia TTS + Silero VAD + STT
Integrations: Cal.com (booking), HubSpot (CRM), Resend (email)
"""
import asyncio
import uuid

from livekit import agents, rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents import llm as lk_llm
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import cartesia as lk_cartesia
from livekit.plugins import openai as lk_openai
from livekit.plugins import silero

from app.agent.context import CallContext
from app.agent.prompt import build_system_prompt
from app.core.call_orchestrator import ALEX_TOOLS
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, set_call_id, set_trace_id
from app.db.models import CallMessage, CallSession
from app.db.session import get_session_factory

logger = get_logger(__name__)


class AlexAgent(Agent):
    def __init__(self, call_ctx: CallContext) -> None:
        settings = get_settings()
        super().__init__(
            instructions=build_system_prompt(call_ctx),
            tools=ALEX_TOOLS,
        )
        self._call_ctx = call_ctx
        self._settings = settings

    async def on_enter(self) -> None:
        greeting = getattr(self._settings, "agent_greeting", None) or (
            'Good morning, LevelOne Agency, Alex speaking<break time="200ms"/>. How can I help you today?'
        )
        await self.session.say(greeting, allow_interruptions=True)

    @agents.utils.log_exceptions(logger=get_logger(__name__))
    def on_user_speech_committed(self, msg: lk_llm.ChatMessage) -> None:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        asyncio.create_task(
            _persist_message(self._call_ctx.call_id, role="user", content=content)
        )

    @agents.utils.log_exceptions(logger=get_logger(__name__))
    def on_agent_speech_committed(self, msg: lk_llm.ChatMessage) -> None:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        asyncio.create_task(
            _persist_message(self._call_ctx.call_id, role="assistant", content=content)
        )


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info("call_started", room=ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Resolve caller number from SIP participant when available
    caller_number = "unknown"
    for participant in ctx.room.remote_participants.values():
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            caller_number = participant.identity or "unknown"
            break

    db_factory = get_session_factory()

    # Try to find a pre-created ringing session from the webhook
    call_id = None
    if caller_number != "unknown":
        from sqlalchemy import select
        async with db_factory() as db:
            result = await db.execute(
                select(CallSession)
                .where(CallSession.caller_number == caller_number)
                .where(CallSession.status == "ringing")
                .order_by(CallSession.started_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                call_id = existing.id
                existing.livekit_room = ctx.room.name
                existing.status = "active"
                await db.commit()
                logger.info("linked_to_webhook_session", call_id=call_id)

    # Fallback to generating a unique session ID
    if not call_id:
        call_id = str(uuid.uuid4())
        async with db_factory() as db:
            db.add(CallSession(
                id=call_id,
                caller_number=caller_number,
                livekit_room=ctx.room.name,
                status="active",
            ))
            await db.commit()
            logger.info("created_new_session", call_id=call_id)

    set_call_id(call_id)

    call_ctx = CallContext(
        call_id=call_id,
        caller_number=caller_number,
        livekit_room=ctx.room.name,
    )

    session = AgentSession[CallContext](
        vad=silero.VAD.load(
            # Still needed for speech-start detection, but no longer in the
            # end-of-turn critical path thanks to turn_detection="stt" below.
            sample_rate=8000,
            min_silence_duration=0.2,
            min_speech_duration=0.05,
            prefix_padding_duration=0.2,
            activation_threshold=0.5,
            deactivation_threshold=0.35,
        ),
        stt=lk_openai.STT(
            model=settings.openai_stt_model,
            api_key=settings.openai_api_key,
            # use_realtime=True → OpenAI Realtime API with server-side VAD.
            # This eliminates Silero from the end-of-turn critical path entirely.
            # The server detects speech boundaries — no local ML inference needed.
            use_realtime=True,
        ),
        llm=lk_openai.LLM(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        ),
        tts=lk_cartesia.TTS(
            model=settings.cartesia_model,
            voice=settings.cartesia_voice_id,
            api_key=settings.cartesia_api_key,
        ),
        # turn_detection is now handled server-side by OpenAI Realtime STT.
        # No need to specify it explicitly — the realtime STT manages end-of-turn.
        userdata=call_ctx,
    )


    await session.start(
        room=ctx.room,
        agent=AlexAgent(call_ctx),
    )

    logger.info("agent_started", call_id=call_id, caller=caller_number)

    @ctx.room.on("disconnected")
    def on_disconnect(_: rtc.DisconnectReason) -> None:
        logger.info("call_ended", call_id=call_id)


async def _persist_message(call_id: str, role: str, content: str) -> None:
    """Write a conversation turn to call_messages. Fire-and-forget via create_task."""
    if not content or not content.strip():
        return
    try:
        factory = get_session_factory()
        async with factory() as db:
            db.add(CallMessage(
                session_id=call_id,
                role=role,
                content=content.strip(),
            ))
            await db.commit()
    except Exception as exc:
        logger.error("persist_message_error", error=str(exc), call_id=call_id, role=role)


def main() -> None:
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    
    configure_logging()
    # NOTE: migrations are the server's (app.main) responsibility.
    # The worker only initialises the DB session factory — no schema changes here.
    get_session_factory()

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=agents.WorkerType.ROOM,
            port=8082,
        ),
    )


if __name__ == "__main__":
    main()
