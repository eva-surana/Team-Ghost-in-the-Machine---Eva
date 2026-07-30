"""
app/logging_config.py — Structured logging configuration.

Provides two modes (controlled by LOG_FORMAT env var):
  "json"  → newline-delimited JSON, parseable by any log aggregator
  "text"  → human-readable with colour-coded levels (default for development)

Request IDs injected by RequestIdMiddleware in app/main.py are forwarded
to the log record via a context variable, so every log line emitted during
a request automatically includes the request_id field.

Usage:
    from app.logging_config import configure_logging
    configure_logging()  # called once at startup before anything else
"""
from __future__ import annotations

import json
import logging
import sys
import contextvars
from datetime import datetime, timezone

# Context variable: set per-request by RequestIdMiddleware
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    _LEVEL_MAP = {
        logging.DEBUG:    "DEBUG",
        logging.INFO:     "INFO",
        logging.WARNING:  "WARNING",
        logging.ERROR:    "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts":         datetime.now(timezone.utc).isoformat(),
            "level":      self._LEVEL_MAP.get(record.levelno, record.levelname),
            "logger":     record.name,
            "msg":        record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter with ANSI colour for development."""

    _COLOURS = {
        "DEBUG":    "\033[36m",    # cyan
        "INFO":     "\033[32m",    # green
        "WARNING":  "\033[33m",    # yellow
        "ERROR":    "\033[31m",    # red
        "CRITICAL": "\033[35m",    # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        rid = request_id_var.get("-")
        rid_part = f" [{rid[:8]}]" if rid != "-" else ""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"{ts} {colour}{record.levelname:8s}{self._RESET}{rid_part} {record.name}"
        msg = record.getMessage()
        formatted = f"{prefix} — {msg}"
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted


def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """
    Configure root logger. Call once at application startup.

    Args:
        log_format: "json" for structured logs, "text" for human-readable.
        log_level:  Standard level name ("DEBUG", "INFO", "WARNING", "ERROR").
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter: logging.Formatter
    if log_format.lower() == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any existing handlers (e.g. basicConfig defaults)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
