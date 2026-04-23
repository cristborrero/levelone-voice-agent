"""
LLM Router — dispatches tasks to the right provider/model based on config.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
import yaml


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------

class LLMClient(ABC):
    """Abstract base for all LLM provider clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        """Send messages and return the assistant reply as a string."""


# ---------------------------------------------------------------------------
# OpenAI-compatible client (works for OpenAI + Groq + OpenRouter)
# ---------------------------------------------------------------------------

class OpenAICompatibleClient(LLMClient):
    """Generic client for any OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Named factory helpers
# ---------------------------------------------------------------------------

def _make_openai_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url="https://api.openai.com/v1",
    )


def _make_groq_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )


_PROVIDER_FACTORIES = {
    "openai": _make_openai_client,
    "groq": _make_groq_client,
}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class LLMRouter:
    """
    Reads config/llm_profiles.yaml and dispatches tasks to the right client.

    Usage:
        router = LLMRouter()
        reply = await router.run("summary", messages=[...])
    """

    _CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "llm_profiles.yaml"

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or self._CONFIG_PATH
        self._config: dict = {}
        self._clients: dict[str, LLMClient] = {}
        self._load_config()

    def _load_config(self) -> None:
        with open(self._config_path) as f:
            self._config = yaml.safe_load(f)

    def reload(self) -> None:
        """Hot-reload config without restarting the process."""
        self._load_config()
        self._clients.clear()

    def _get_client(self, provider: str) -> LLMClient:
        if provider not in self._clients:
            factory = _PROVIDER_FACTORIES.get(provider)
            if not factory:
                raise ValueError(f"Unknown LLM provider: '{provider}'")
            self._clients[provider] = factory()
        return self._clients[provider]

    async def run(
        self,
        task: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        tasks = self._config.get("tasks", {})
        if task not in tasks:
            raise KeyError(f"Task '{task}' not found in llm_profiles.yaml")

        task_cfg = tasks[task]
        provider = task_cfg["provider"]
        model = task_cfg["model"]
        fallback = task_cfg.get("fallback")

        try:
            client = self._get_client(provider)
            return await client.chat(messages=messages, model=model, **kwargs)
        except Exception as primary_err:
            if not fallback:
                raise
            try:
                fb_client = self._get_client(fallback["provider"])
                return await fb_client.chat(
                    messages=messages, model=fallback["model"], **kwargs
                )
            except Exception:
                raise primary_err

    def get_task_config(self, task: str) -> dict:
        return self._config.get("tasks", {}).get(task, {})

    def get_all_tasks(self) -> dict:
        return self._config.get("tasks", {})

    def get_providers(self) -> dict:
        return self._config.get("providers", {})

    def update_task(self, task: str, provider: str, model: str) -> None:
        """Update a task mapping and persist to disk."""
        if task not in self._config.get("tasks", {}):
            raise KeyError(f"Task '{task}' does not exist")
        allowed = self._config.get("providers", {})
        if provider not in allowed:
            raise ValueError(f"Provider '{provider}' not in whitelist")
        if model not in allowed[provider].get("models", []):
            raise ValueError(f"Model '{model}' not available for provider '{provider}'")
        self._config["tasks"][task]["provider"] = provider
        self._config["tasks"][task]["model"] = model
        with open(self._config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        self._clients.clear()  # force reconnect with new config


# Singleton for import convenience
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
