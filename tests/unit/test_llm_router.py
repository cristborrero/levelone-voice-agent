"""Unit tests for LLMRouter — persona injection, routing, fallback, reload."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from app.llm.router import LLMRouter, OpenAICompatibleClient


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    "tasks": {
        "summary": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "persona": "agent_personas/summary.txt",
            "fallback": None,
        },
        "call_brain": {
            "provider": "openai",
            "model": "gpt-4o",
            "fallback": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
            },
        },
    },
    "providers": {
        "openai": {"models": ["gpt-4o", "gpt-4o-mini"]},
        "groq": {"models": ["llama-3.3-70b-versatile"]},
    },
}

PERSONA_TEXT = "You are a Sales Coach. Be structured and concise."
USER_MSG = [{"role": "user", "content": "Summarise this call."}]


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Write a minimal config + persona file to a temp directory."""
    cfg_path = tmp_path / "llm_profiles.yaml"
    cfg_path.write_text(yaml.dump(MINIMAL_CONFIG), encoding="utf-8")

    persona_dir = tmp_path / "agent_personas"
    persona_dir.mkdir()
    (persona_dir / "summary.txt").write_text(PERSONA_TEXT, encoding="utf-8")

    return tmp_path


@pytest.fixture()
def router(config_dir: Path) -> LLMRouter:
    """LLMRouter pointed at the temp config dir."""
    cfg_path = config_dir / "llm_profiles.yaml"
    r = LLMRouter(config_path=cfg_path)
    # Override _CONFIG_DIR so _load_persona resolves relative to tmp dir
    r._CONFIG_DIR = config_dir
    return r


# ---------------------------------------------------------------------------
# _inject_persona
# ---------------------------------------------------------------------------

class TestInjectPersona:
    def test_prepends_system_message_when_absent(self, router: LLMRouter) -> None:
        result = router._inject_persona(USER_MSG, PERSONA_TEXT)
        assert result[0] == {"role": "system", "content": PERSONA_TEXT}
        assert result[1:] == USER_MSG

    def test_skips_injection_when_system_already_present(self, router: LLMRouter) -> None:
        existing_system = {"role": "system", "content": "Custom override."}
        messages = [existing_system, *USER_MSG]
        result = router._inject_persona(messages, PERSONA_TEXT)
        assert result[0] is existing_system
        assert len(result) == 2

    def test_empty_messages_gets_system_prepended(self, router: LLMRouter) -> None:
        result = router._inject_persona([], PERSONA_TEXT)
        assert result == [{"role": "system", "content": PERSONA_TEXT}]


# ---------------------------------------------------------------------------
# _load_persona
# ---------------------------------------------------------------------------

class TestLoadPersona:
    def test_loads_persona_text_correctly(self, router: LLMRouter) -> None:
        text = router._load_persona("agent_personas/summary.txt")
        assert text == PERSONA_TEXT

    def test_caches_on_second_call(self, router: LLMRouter, config_dir: Path) -> None:
        router._load_persona("agent_personas/summary.txt")
        # Overwrite file on disk — second call must still return original (cached)
        (config_dir / "agent_personas" / "summary.txt").write_text("NEW CONTENT")
        text = router._load_persona("agent_personas/summary.txt")
        assert text == PERSONA_TEXT

    def test_raises_for_missing_file(self, router: LLMRouter) -> None:
        with pytest.raises(FileNotFoundError):
            router._load_persona("agent_personas/nonexistent.txt")


# ---------------------------------------------------------------------------
# run — persona injection end-to-end
# ---------------------------------------------------------------------------

class TestRunPersonaInjection:
    async def test_persona_injected_for_task_with_persona(self, router: LLMRouter) -> None:
        captured: list[list[dict]] = []

        async def fake_chat(messages: list[dict], model: str, **_: object) -> str:
            captured.append(messages)
            return "ok"

        mock_client = MagicMock()
        mock_client.chat = fake_chat
        router._clients["groq"] = mock_client

        await router.run("summary", messages=list(USER_MSG))

        assert captured[0][0]["role"] == "system"
        assert captured[0][0]["content"] == PERSONA_TEXT

    async def test_no_persona_injected_for_task_without_persona(
        self, router: LLMRouter
    ) -> None:
        captured: list[list[dict]] = []

        async def fake_chat(messages: list[dict], model: str, **_: object) -> str:
            captured.append(messages)
            return "ok"

        mock_client = MagicMock()
        mock_client.chat = fake_chat
        router._clients["openai"] = mock_client

        await router.run("call_brain", messages=list(USER_MSG))

        assert captured[0][0]["role"] == "user"

    async def test_existing_system_message_not_overwritten(
        self, router: LLMRouter
    ) -> None:
        captured: list[list[dict]] = []
        custom_system = {"role": "system", "content": "Custom instructions."}

        async def fake_chat(messages: list[dict], model: str, **_: object) -> str:
            captured.append(messages)
            return "ok"

        mock_client = MagicMock()
        mock_client.chat = fake_chat
        router._clients["groq"] = mock_client

        await router.run("summary", messages=[custom_system, *USER_MSG])

        assert captured[0][0]["content"] == "Custom instructions."


# ---------------------------------------------------------------------------
# run — fallback
# ---------------------------------------------------------------------------

class TestRunFallback:
    async def test_falls_back_to_secondary_provider_on_primary_error(
        self, router: LLMRouter
    ) -> None:
        failing_client = MagicMock()
        failing_client.chat = AsyncMock(side_effect=Exception("timeout"))
        router._clients["openai"] = failing_client

        fallback_client = MagicMock()
        fallback_client.chat = AsyncMock(return_value="fallback reply")
        router._clients["groq"] = fallback_client

        result = await router.run("call_brain", messages=list(USER_MSG))
        assert result == "fallback reply"

    async def test_raises_primary_error_when_no_fallback_configured(
        self, router: LLMRouter
    ) -> None:
        failing_client = MagicMock()
        failing_client.chat = AsyncMock(side_effect=RuntimeError("groq down"))
        router._clients["groq"] = failing_client

        with pytest.raises(RuntimeError, match="groq down"):
            await router.run("summary", messages=list(USER_MSG))

    async def test_raises_primary_error_when_both_providers_fail(
        self, router: LLMRouter
    ) -> None:
        primary = MagicMock()
        primary.chat = AsyncMock(side_effect=RuntimeError("openai down"))
        router._clients["openai"] = primary

        secondary = MagicMock()
        secondary.chat = AsyncMock(side_effect=RuntimeError("groq also down"))
        router._clients["groq"] = secondary

        with pytest.raises(RuntimeError, match="openai down"):
            await router.run("call_brain", messages=list(USER_MSG))


# ---------------------------------------------------------------------------
# run — unknown task
# ---------------------------------------------------------------------------

class TestRunUnknownTask:
    async def test_raises_key_error_for_unknown_task(self, router: LLMRouter) -> None:
        with pytest.raises(KeyError, match="ghost_task"):
            await router.run("ghost_task", messages=list(USER_MSG))


# ---------------------------------------------------------------------------
# reload
# ---------------------------------------------------------------------------

class TestReload:
    def test_reload_clears_persona_cache(
        self, router: LLMRouter, config_dir: Path
    ) -> None:
        router._load_persona("agent_personas/summary.txt")
        assert "agent_personas/summary.txt" in router._persona_cache

        (config_dir / "agent_personas" / "summary.txt").write_text("UPDATED PERSONA")
        router.reload()

        assert router._persona_cache == {}
        text = router._load_persona("agent_personas/summary.txt")
        assert text == "UPDATED PERSONA"

    def test_reload_clears_client_cache(self, router: LLMRouter) -> None:
        router._clients["groq"] = MagicMock()
        router.reload()
        assert router._clients == {}
