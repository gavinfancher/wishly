"""Structured (JSON) logging setup for Wishly.

Uses only the standard library so it works identically under FastAPI/uvicorn and
under the Prefect worker. Call :func:`configure_logging` once at process startup; obtain
loggers via :func:`get_logger`.

In ``dev`` the level defaults to ``DEBUG`` and in ``prod`` to ``INFO``. Logs are
emitted as one JSON object per line to stdout, which plays well with container
log collectors.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any

from wishly.core.settings import settings

# Attributes present on every ``logging.LogRecord``; anything *not* in this set
# is treated as caller-supplied structured context (``logger.info(..., extra=...)``).
_RESERVED_RECORD_ATTRS = frozenset(
    vars(logging.makeLogRecord({})).keys() | {"message", "asctime", "taskName"}
)


class JsonFormatter(logging.Formatter):
    """Render a :class:`logging.LogRecord` as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # Merge any structured context passed via ``extra=...``.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int | str | None = None) -> None:
    """Configure root logging to emit structured JSON to stdout.

    Idempotent: replaces existing handlers so repeated calls (e.g. in tests or
    under autoreload) do not duplicate output.

    Args:
        level: Optional explicit level; defaults to ``DEBUG`` in dev, else ``INFO``.
    """
    if level is None:
        level = logging.DEBUG if settings.environment == "dev" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a named logger (defaults to the package root logger)."""
    return logging.getLogger(name if name is not None else "wishly")
