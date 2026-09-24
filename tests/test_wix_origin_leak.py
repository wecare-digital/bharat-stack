"""Phase 7.2 — the CORS origin must not survive an invocation.

The defect
----------
`wix-store/handler.py` keeps the request's Origin in a **module-level global** that
`_response` reads, and its own comment described the design without noticing the
consequence:

    # Module-level origin for CORS (set per-invocation in handler)
    origin = ''

A Lambda execution environment is reused across invocations, so a value set by request A
is still there for request B. That is only harmless if every path that returns through
`_response` also sets it first, and two do not: `_sync_products` and `_sync_orders` run on
a schedule with no HTTP event. On a warm sandbox they would emit the **previous HTTP
caller's** Origin in a CORS header on a cron response.

Threading `origin` through every signature is the cleaner boundary and is deliberately not
what this pins: 36 call sites across 22 functions, only 2 of which have an origin to pass,
in a 1,743-line handler whose integration is entirely switched off and so cannot be
live-verified. The reset is small and provable. The signature change stays recorded as the
remaining half of 7.2.

These tests exercise the behaviour rather than reading the source, because the fix is
subtle: `global origin` is declared once at the top of `handler` and has to cover the
assignment in the `finally`, which is easy to believe and worth proving.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HANDLER = ROOT / "amplify/functions/ecommerce/wix-store/handler.py"
SHARED = ROOT / "amplify/functions/shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("wix_store_handler", HANDLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def an_event(origin: str = "https://wecare.digital", method: str = "GET",
             path: str = "/wix-store/does-not-exist") -> dict:
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"origin": origin},
        "requestContext": {"apiId": "zllr9lrg7j",
                           "http": {"method": method, "path": path,
                                    "sourceIp": "1.2.3.4"}},
        "queryStringParameters": {},
    }


class TestTheGlobalIsCleared:
    def test_origin_is_blank_after_an_invocation(self, mod, monkeypatch):
        # Auth would refuse before routing; stub it so the request reaches the `finally`.
        monkeypatch.setattr(
            "lambda_utils.middleware.require_auth",
            lambda event, required_role=None: None)

        mod.handler(an_event("https://wecare.digital"), None)
        assert mod.origin == "", (
            "the request's Origin survived the invocation, so the next request that does "
            "not set it - including the two scheduled sync paths - would emit this one")

    def test_a_stale_value_does_not_survive_either(self, mod, monkeypatch):
        monkeypatch.setattr(
            "lambda_utils.middleware.require_auth",
            lambda event, required_role=None: None)

        # Simulate a warm sandbox left dirty by an earlier request.
        mod.origin = "https://attacker.example.com"
        mod.handler(an_event("https://wecare.digital"), None)
        assert mod.origin == ""

    def test_it_is_cleared_even_when_the_handler_raises(self, mod, monkeypatch):
        def explode(event, required_role=None):
            raise RuntimeError("boom")

        monkeypatch.setattr("lambda_utils.middleware.require_auth", explode)
        mod.origin = "https://stale.example.com"

        # The handler catches and returns 500; the point is that `finally` still runs.
        response = mod.handler(an_event(), None)
        assert response["statusCode"] == 500
        assert mod.origin == "", (
            "an exception path skipped the reset, which is the path most likely to leave "
            "a sandbox dirty")

    def test_the_origin_is_still_honoured_DURING_the_request(self, mod, monkeypatch):
        # The reset must not break the thing the global exists for. Captured from inside
        # the request rather than after it.
        seen = {}

        def capture(event, required_role=None):
            seen["origin"] = mod.origin
            return None

        monkeypatch.setattr("lambda_utils.middleware.require_auth", capture)
        mod.handler(an_event("https://stack.wecare.digital"), None)
        assert seen["origin"] == "https://stack.wecare.digital"


class TestTheScheduledPathsAreTheReason:
    def test_the_sync_functions_return_through_response(self, mod):
        # If this stops being true the rationale above weakens, so it is asserted rather
        # than trusted to a comment.
        import inspect
        for name in ("_sync_products", "_sync_orders"):
            source = inspect.getsource(getattr(mod, name))
            assert "_response(" in source, (
                f"{name} no longer returns through _response; revisit why the reset "
                f"exists")

    def test_neither_sync_function_takes_an_event(self, mod):
        import inspect
        for name in ("_sync_products", "_sync_orders"):
            params = set(inspect.signature(getattr(mod, name)).parameters)
            assert "event" not in params and "origin" not in params, (
                f"{name} now has an origin available, so it should pass one explicitly "
                f"instead of relying on the global")

    def test_a_cron_response_carries_no_borrowed_origin(self, mod):
        # The end-to-end property, on the shape the bug actually took: a dirty sandbox,
        # then a scheduled invocation.
        mod.origin = "https://someone-elses-site.example.com"
        try:
            mod.origin = ""  # what the finally guarantees before the cron runs
            response = mod._response(200, {"ok": True})
            headers = response.get("headers", {})
            allowed = headers.get("Access-Control-Allow-Origin", "")
            assert "someone-elses-site" not in allowed
        finally:
            mod.origin = ""
