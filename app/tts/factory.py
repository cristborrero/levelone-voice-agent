from livekit.plugins import cartesia as lk_cartesia

from app.core.config import get_settings


def create_tts() -> lk_cartesia.TTS:
    settings = get_settings()
    return lk_cartesia.TTS(
        model=settings.cartesia_model,
        voice=settings.cartesia_voice_id,
        api_key=settings.cartesia_api_key,
        language=settings.agent_language,
    )
