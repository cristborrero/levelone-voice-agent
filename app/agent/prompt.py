from datetime import date
from pathlib import Path

from app.agent.context import CallContext

_SYSTEM_PROMPT = (Path(__file__).parent.parent.parent / "config" / "prompts" / "alex_system.txt").read_text()


def build_system_prompt(ctx: CallContext, hubspot_context: str = "") -> str:
    return _SYSTEM_PROMPT.format(
        current_date=date.today().isoformat(),
        caller_number=ctx.caller_number,
        hubspot_context=hubspot_context,
    )


def build_messages(ctx: CallContext, hubspot_context: str = "") -> list[dict[str, str]]:
    system = build_system_prompt(ctx, hubspot_context)
    return [{"role": "system", "content": system}, *ctx.messages]
