"""
Structured JSON logging for Lambda handlers.

Usage:
    from lambda_utils.logging import get_logger, log_event

    logger = get_logger(__name__)
    log_event(logger, 'message_sent', contactId='abc', channel='WHATSAPP')
"""

import os
import json
import logging
from typing import Any


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a logger configured with the LOG_LEVEL env var.
    Defaults to INFO.
    """
    logger = logging.getLogger(name)
    level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


def log_event(logger: logging.Logger, event_name: str, level: str = 'info', **kwargs: Any) -> None:
    """
    Emit a structured JSON log line.
    All kwargs are included as top-level keys in the JSON payload.
    """
    payload = {'event': event_name, **kwargs}
    log_fn = getattr(logger, level, logger.info)
    log_fn(json.dumps(payload, default=str))
