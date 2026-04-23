from livekit.plugins import openai as lk_openai

from app.core.config import get_settings


def create_stt() -> lk_openai.STT:
    settings = get_settings()
    return lk_openai.STT(
        model=settings.openai_stt_model,
        api_key=settings.openai_api_key,
        language=settings.agent_language,
    )
