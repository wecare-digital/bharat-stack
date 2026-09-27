"""
Test configuration — handles module isolation for Lambda handlers.

All Lambda handlers are named handler.py, so we need to clear the module
cache between test files to avoid import collisions.
"""
import sys
import os
import pytest

# A REGION FOR boto3, SET BEFORE ANY HANDLER IS IMPORTED.
#
# Lambda handlers build their clients at module scope - url-shortener/handler.py:31 is
# `dynamodb = boto3.resource("dynamodb")` - which is the right pattern in Lambda, because the
# client is then reused across invocations and the region arrives from the execution
# environment. It does mean IMPORTING such a handler needs a region, and several tests import
# one on purpose: tests/test_url_shortener_base.py reloads it once per case because the
# short-link base is computed at import time and cannot be re-read afterwards.
#
# CI provides no region. route-auth.yml sets neither AWS_DEFAULT_REGION nor AWS_REGION, and
# the "Full python suite" step assumes no AWS context at all. So boto3 raised
# `botocore.exceptions.NoRegionError: You must specify a region.` during import, before any
# test body ran, and 7 tests failed on every push while 3514 passed. The job is a BLOCKING
# gate, so it had been permanently red and therefore told nobody anything - the same failure
# mode the comment above the dependency step in that workflow describes for a collection error.
#
# It passed locally, which is why it survived: a developer machine almost always has a region
# in the environment or in ~/.aws/config. The suite only fails where there is no AWS config at
# all, i.e. exactly in CI.
#
# setdefault, NOT an assignment: a real region in the environment must win, so this cannot
# retarget anyone's deliberate configuration. us-east-1 matches the region this project
# actually deploys to, so any endpoint a test constructs is the realistic one.
#
# DELIBERATELY NO DUMMY CREDENTIALS. A region alone does not grant access, so a test that
# accidentally reaches for real AWS still fails - which is the behaviour worth keeping. Fake
# credentials here would hide that.
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')

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
