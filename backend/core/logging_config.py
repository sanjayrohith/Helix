"""Logging setup for the HELIX backend.

Two formats are supported: a coloured, human-friendly console format for local
development, and single-line JSON for container/log-aggregation environments
(``HELIX_LOG_JSON=true``). Both carry the correlation id attached by the
request-context middleware when one is present.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

from core.config import settings

# Correlation id for the in-flight request, populated by middleware.
request_id_var: ContextVar[str | None] = ContextVar("helix_request_id", default=None)

_LEVEL_COLOURS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class RequestIdFilter(logging.Filter):
    """Copy the current request id onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "request_id":
                payload[key] = value
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Compact, colourised console output."""

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelname, "")
        stamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        request_id = getattr(record, "request_id", "-")
        suffix = f" [{request_id[:8]}]" if request_id and request_id != "-" else ""
        head = f"{stamp} {colour}{record.levelname:<8}{_RESET} {record.name}{suffix}"
        text = f"{head} | {record.getMessage()}"
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


def configure_logging() -> None:
    """Install the HELIX root logging handler. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(settings.log_level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else ConsoleFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    # uvicorn installs its own noisy access logger; route it through ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    logging.getLogger("helix").debug("Logging configured (level=%s)", settings.log_level)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced HELIX logger."""
    return logging.getLogger(f"helix.{name}" if not name.startswith("helix") else name)
