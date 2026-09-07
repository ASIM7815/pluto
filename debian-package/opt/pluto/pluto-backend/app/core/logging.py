"""Structured logging for PLUTO backend"""
import structlog
import logging
from app.core.config import settings


def configure_logging():
    """Configure structured logging"""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.pluto_log_level.upper()),
    )
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.pluto_log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str):
    """Get a structured logger instance"""
    return structlog.get_logger(name)
