import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from app.core.config import LogFormat, get_settings

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_call_id: ContextVar[str] = ContextVar("call_id", default="")


def set_trace_id(trace_id: str) -> None:
    _trace_id.set(trace_id)


def set_call_id(call_id: str) -> None:
    _call_id.set(call_id)


def _add_call_context(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    if trace_id := _trace_id.get():
        event_dict["trace_id"] = trace_id
    if call_id := _call_id.get():
        event_dict["call_id"] = call_id
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.app_log_level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_call_context,
    ]

    if settings.app_log_format == LogFormat.JSON:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "livekit", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
