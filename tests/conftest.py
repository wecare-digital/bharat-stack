"""
Test configuration — handles module isolation for Lambda handlers.

All Lambda handlers are named handler.py, so we need to clear the module
cache between test files to avoid import collisions.
"""
import sys
import os
import pytest

# Ensure shared lambda_utils is always importable
_shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
if _shared_path not in sys.path:
    sys.path.insert(0, _shared_path)

# Base path for all handler directories
_functions_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions'))


def _clean_handler_paths():
    """Remove all handler-specific paths from sys.path (keep shared lambda_utils)."""
    sys.path[:] = [
        p for p in sys.path
        if not (os.path.abspath(p).startswith(_functions_base) and os.path.abspath(p) != _shared_path)
    ]


@pytest.fixture(autouse=True, scope='function')
def isolate_handler_imports():
    """Clear cached handler module between tests to avoid cross-contamination.
    
    Each test file inserts its handler path at module level. We clear the handler
    module from sys.modules so the next import picks up the correct handler.
    We also clean stale handler paths so only the current test file's path remains.
    """
    # Clear handler module cache
    for mod_name in list(sys.modules.keys()):
        if mod_name == 'handler' or mod_name.startswith('handler.'):
            del sys.modules[mod_name]
    yield
    for mod_name in list(sys.modules.keys()):
        if mod_name == 'handler' or mod_name.startswith('handler.'):
            del sys.modules[mod_name]
