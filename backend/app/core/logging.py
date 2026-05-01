"""
Structured logging. JSON in prod/demo, pretty in dev (see config LOG_FORMAT).
"""
from __future__ import annotations

import logging
import sys

from app.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    if settings.LOG_FORMAT == "json":
        try:
            from pythonjsonlogger import jsonlogger
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(jsonlogger.JsonFormatter())
            logging.root.addHandler(handler)
            logging.root.setLevel(level)
        except ImportError:
            logging.basicConfig(level=level, stream=sys.stdout)
    else:
        logging.basicConfig(
            level=level,
            stream=sys.stdout,
            format="%(levelname)s [%(name)s] %(message)s",
        )
