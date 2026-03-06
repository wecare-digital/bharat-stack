"""
Shared pytest fixtures for WECARE.DIGITAL tests.
"""
import sys
import os
import pytest

# Add shared lambda_utils to path so tests can import them
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))


@pytest.fixture
def api_event():
    """Minimal API Gateway / Function URL event."""
    return {
        'requestContext': {'http': {'method': 'POST', 'path': '/test'}},
        'headers': {'origin': 'https://stack.wecare.digital', 'authorization': 'Bearer test-token'},
        'body': '{"key": "value"}',
        'isBase64Encoded': False,
    }


@pytest.fixture
def options_event():
    """OPTIONS preflight event."""
    return {
        'requestContext': {'http': {'method': 'OPTIONS', 'path': '/test'}},
        'headers': {'origin': 'https://stack.wecare.digital'},
        'body': None,
    }


@pytest.fixture
def lambda_event():
    """Lambda-to-Lambda invocation event (no HTTP context)."""
    return {
        'action': 'process',
        'payload': {'contactId': 'c123'},
    }
