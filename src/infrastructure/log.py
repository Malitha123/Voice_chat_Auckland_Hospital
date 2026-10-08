"""
Centralised logging configuration — powered by **loguru**.

Usage (any module)::

    from loguru import logger
    logger.info("Hello")
    logger.success("Done ✅")

Usage (entry-points — services, scripts, CLI)::

    from infrastructure.log import setup_logging
    setup_logging()              # defaults: INFO, stderr
    setup_logging("DEBUG")       # more verbose

Design:
    - ``loguru`` replaces stdlib ``logging`` everywhere.
    - A single ``setup_logging()`` call at the entry-point configures
      format, level, and optionally intercepts stdlib ``logging`` so
      third-party libraries (SQLAlchemy, httpx, etc.) also route
      through loguru.
    - No per-module ``getLogger(__name__)`` setup is required.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from loguru import logger


# ── Format strings ────────────────────────────────────────────

_FMT_FULL = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
    "<level>{message}</level>"
)


# ── Intercept handler ────────────────────────────────────────

class _InterceptHandler(logging.Handler):
    """Route stdlib ``logging`` records into **loguru**.

    Attach this handler to the root logger so that libraries which use
    ``logging.getLogger(…)`` (SQLAlchemy, httpx, LangChain, etc.)
    automatically emit through loguru's sinks.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Map stdlib level to loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the caller frame that originated the log call
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ── Public API ────────────────────────────────────────────────

def setup_logging(
    level: str = "INFO",
    *,
    intercept_stdlib: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure loguru for the current process.

    Call this once at the process entry point.

    Args:
        level: Minimum log level (``DEBUG``, ``INFO``, ``WARNING``, …).
        intercept_stdlib: Route stdlib ``logging`` through loguru so
                         third-party libraries also emit structured logs.
        log_file: Optional path to a rotating log file.
    """
    # Remove default loguru handler (id 0)
    logger.remove()

    # Primary sink: stderr
    logger.add(
        sys.stderr,
        format=_FMT_FULL,
        level=level.upper(),
        colorize=True,
        backtrace=True,
        diagnose=False,  # keep tracebacks concise in production
    )

    # Optional file sink
    if log_file:
        logger.add(
            log_file,
            format=_FMT_FULL,
            level=level.upper(),
            rotation="10 MB",
            retention="7 days",
            compression="gz",
        )

    # Intercept stdlib logging
    if intercept_stdlib:
        logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    logger.debug("Loguru configured — level={}", level)
