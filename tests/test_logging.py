"""Tests for lambda_utils.logging module."""
import json
import logging
import pytest
from lambda_utils.logging import get_logger, log_event


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger('test')
        assert isinstance(logger, logging.Logger)

    def test_default_level_info(self, monkeypatch):
        monkeypatch.delenv('LOG_LEVEL', raising=False)
        logger = get_logger('test_info')
        assert logger.level == logging.INFO

    def test_respects_env_level(self, monkeypatch):
        monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
        logger = get_logger('test_debug')
        assert logger.level == logging.DEBUG

    def test_invalid_level_defaults_info(self, monkeypatch):
        monkeypatch.setenv('LOG_LEVEL', 'INVALID')
        logger = get_logger('test_invalid')
        assert logger.level == logging.INFO


class TestLogEvent:
    def test_emits_json(self, caplog):
        logger = get_logger('test_emit')
        with caplog.at_level(logging.INFO, logger='test_emit'):
            log_event(logger, 'test_event', contactId='c1')
        record = caplog.records[-1]
        payload = json.loads(record.message)
        assert payload['event'] == 'test_event'
        assert payload['contactId'] == 'c1'

    def test_custom_level(self, caplog):
        logger = get_logger('test_level')
        with caplog.at_level(logging.WARNING, logger='test_level'):
            log_event(logger, 'warn_event', level='warning')
        assert len(caplog.records) >= 1
