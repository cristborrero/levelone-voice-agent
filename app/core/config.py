from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # LiveKit
    # -------------------------------------------------------------------------
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    livekit_sip_trunk_username: str = ""
    livekit_sip_trunk_password: str = ""
    livekit_sip_trunk_domain: str = "sip.telnyx.com"

    # -------------------------------------------------------------------------
    # Telnyx
    # -------------------------------------------------------------------------
    telnyx_api_key: str
    telnyx_app_id: str
    telnyx_phone_number: str
    telnyx_webhook_secret: str = ""

    # -------------------------------------------------------------------------
    # OpenAI
    # -------------------------------------------------------------------------
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_stt_model: str = "whisper-1"

    # -------------------------------------------------------------------------
    # Cartesia
    # -------------------------------------------------------------------------
    cartesia_api_key: str
    cartesia_model: str = "sonic-english"
    cartesia_voice_id: str

    # -------------------------------------------------------------------------
    # Groq
    # -------------------------------------------------------------------------
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    # -------------------------------------------------------------------------
    # HubSpot
    # -------------------------------------------------------------------------
    hubspot_access_token: str
    hubspot_owner_id: str = ""

    # -------------------------------------------------------------------------
    # Cal.com
    # -------------------------------------------------------------------------
    calcom_api_key: str
    calcom_event_type_id: str
    calcom_username: str
    calcom_base_url: str = "https://api.cal.com/v2"

    # -------------------------------------------------------------------------
    # Resend
    # -------------------------------------------------------------------------
    resend_api_key: str
    resend_from_email: str = "alex@levelone.agency"
    resend_from_name: str = "Alex from LevelOne"

    # -------------------------------------------------------------------------
    # Agent
    # -------------------------------------------------------------------------
    agent_name: str = "Alex"
    agent_company: str = "LevelOne Agency"
    agent_language: str = "en-GB"
    agent_max_call_duration_seconds: int = Field(default=600, ge=60, le=3600)
    agent_silence_timeout_seconds: int = Field(default=10, ge=3, le=60)
    agent_turn_detection_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    # -------------------------------------------------------------------------
    # LLM Router overrides
    # -------------------------------------------------------------------------
    llm_conversation_provider: str = "openai"
    llm_summarization_provider: str = "groq"
    llm_classification_provider: str = "groq"
    llm_lead_scoring_provider: str = "groq"
    llm_email_draft_provider: str = "groq"

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_log_level: str = "INFO"
    app_log_format: LogFormat = LogFormat.JSON
    database_url: str = "sqlite+aiosqlite:///./data/voice_agent.db"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8080, ge=1024, le=65535)

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Clear cache and reload settings from .env (useful after env changes)."""
    get_settings.cache_clear()
    return get_settings()
