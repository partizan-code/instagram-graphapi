"""Central console logging; no log files or credential loading."""

import sys

from loguru import logger


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
