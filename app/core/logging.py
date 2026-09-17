"""Logging setup.

Every log line carries the ``run_id`` of the story generation it belongs to, so a
single run can be followed across all six graph nodes.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from logging.config import dictConfig

_run_id: ContextVar[str] = ContextVar("run_id", default="-")


def set_run_id(run_id: str) -> None:
    """Bind a run id to the current async context."""
    _run_id.set(run_id)


def get_run_id() -> str:
    """Return the run id bound to the current async context."""
    return _run_id.get()


class RunIdFilter(logging.Filter):
    """Inject the context-local run id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = get_run_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Install the application-wide logging configuration."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"run_id": {"()": RunIdFilter}},
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)-8s [%(run_id)s] %(name)s: %(message)s",
                    "datefmt": "%H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["run_id"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"handlers": ["console"], "level": level.upper()},
            "loggers": {
                # These are chatty at DEBUG and drown out the story pipeline.
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "openai": {"level": "WARNING"},
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
