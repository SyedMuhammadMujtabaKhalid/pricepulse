"""
PricePulse — Structured Logging
================================

Production-grade logging using structlog.

Engineering Decisions:
    1. structlog over stdlib logging:
       - Outputs structured key-value pairs, not unstructured strings.
       - Machine-parseable (JSON mode) for log aggregation tools (ELK, Datadog).
       - Human-readable (console mode) for local development.
       - Automatically adds timestamps, log levels, and caller info.

    2. Two output formats controlled by LOG_FORMAT env var:
       - "console": Colored, human-readable output for local development.
       - "json": Machine-parseable JSON for production/CI environments.

    3. Every log call should include contextual key-value pairs:
           log.info("pipeline.extract.complete", source="bestbuy", records=42)
       This makes logs searchable and filterable without regex.

    4. Logger is configured once at startup via setup_logging().
       All modules use: log = structlog.get_logger()

Usage:
    from src.core.logger import setup_logging
    import structlog

    setup_logging()  # Call once at app startup
    log = structlog.get_logger()

    log.info("pipeline.started", run_id="run_001")
    log.warning("source.slow", source="scraper", latency_ms=5200)
    log.error("database.connection_failed", host="localhost", port=5432)
"""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """
    Configure structlog for the entire application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format — "console" for human-readable, "json" for machine.

    Why this setup?
        structlog wraps stdlib logging but adds structure. We configure both:
        - structlog processors (add timestamp, level, format output)
        - stdlib root logger (so third-party libs like SQLAlchemy also get formatted)
    """
    # Determine the numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Shared processors (run on every log event) ─────────────
    shared_processors: list[structlog.types.Processor] = [
        # Add log level as a string (e.g., "info", "error")
        structlog.stdlib.add_log_level,
        # Add logger name (e.g., "src.pipeline.runner")
        structlog.stdlib.add_logger_name,
        # Add ISO8601 timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Merge thread-local context (useful for request tracking)
        structlog.contextvars.merge_contextvars,
        # Unpack exceptions into readable tracebacks
        structlog.processors.format_exc_info,
        # Remove internal structlog keys that clutter output
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # ── Choose renderer based on format ─────────────────────────
    if log_format.lower() == "json":
        # Production: machine-parseable JSON, one line per event
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored, human-readable console output
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),  # Only colorize if terminal supports it
        )

    # ── Configure structlog ─────────────────────────────────────
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Configure stdlib root logger ────────────────────────────
    # This ensures third-party libraries (SQLAlchemy, httpx) also
    # produce structured output through our formatter.
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Quiet down noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Optional logger name. If not provided, structlog auto-detects
              the calling module name.

    Returns:
        A bound logger with structured output.

    Usage:
        log = get_logger(__name__)
        log.info("task.complete", duration_ms=1234)
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
