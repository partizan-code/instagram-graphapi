"""Central console logging; no log files or credential loading."""

import sys

from loguru import logger

# Uvicorn access/error logs may contain query parameters or raw exceptions.
# Application lifecycle and request summaries use the shared Loguru logger.
UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        name: {"handlers": ["null"], "propagate": False}
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")
    },
}


def configure_logging() -> None:
    """Configure one synchronous stderr sink; repeated setup never duplicates records."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}",
        colorize=False,
        backtrace=False,
        diagnose=False,
    )
