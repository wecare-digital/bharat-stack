"""A `urllib.request.urlopen` replacement for the Wix HTTP boundary. One stub, two callers.

Design reference: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` §2.3.

The boundary is cut at `urlopen` and nowhere higher, so every behaviour of
`wix_ecom._request` executes for real: header composition, `json.dumps` with no custom encoder,
the `HTTPError`-to-status-prose reduction, and `json.loads` with no `parse_float`. Stubbing
`_request` itself would stub out the four conversion rules the harness exists to measure.

WHY THE REFUSAL IS NOT AN `Exception`
-------------------------------------
`wix_ecom._request` ends in a bare `except Exception` that converts anything it catches into a
`WixEcomError` (`wix_ecom.py:109-111`, the enclosing `try:` at `:103`), and
`coupons/handler._create` then catches `Exception` and answers **202** with a
documented-success body (`handler.py:229-233`). An `AssertionError` raised here would therefore
be laundered first into a transport error and then into a success - which is exactly the
"passing quietly" this stub exists to prevent, and it would defeat the resolve-before-create
property the harness leans on entirely. `UnexpectedWixCall` is a `BaseException` and escapes
both.

Plain `AssertionError` is kept only for assertions made OUTSIDE a stubbed call, where nothing
is catching.

WHAT IS REDACTED, AND WHAT DELIBERATELY IS NOT
----------------------------------------------
`Authorization` is replaced by `"<redacted>"` **at capture**, so `RecordedRequest` never holds
the value at all. A pytest failure diff, a `--json` transcript and a CI log therefore cannot
carry it even in principle. The value is a placeholder today; the structure is what must survive
the day somebody points the harness at a real key by accident.

`body_bytes` and `body` are recorded **verbatim**, so a gift-card code travelling in a
`find_by_code` filter IS recorded. That is deliberate rather than a hole, and it rests on one
fact: every gift-card code anywhere in this harness or the demo is a fixture placeholder,
because the transport is stubbed unconditionally and there is no code path, flag or environment
in which a live Wix response reaches the process. The credential is treated differently because
`wix_ecom._key_cache` is a module global a future test could seed from Secrets Manager by
accident - a real key CAN arrive in this process in a way a real code cannot.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class UnexpectedWixCall(BaseException):
    """Deliberately NOT an Exception, so production error handling cannot swallow it.

    `wix_ecom._request` ends in `except Exception` and `coupons/handler._create` catches
    Exception and answers 202. An AssertionError from this stub would therefore be reported
    as a successful, documented outcome. BaseException escapes both.
    """


@dataclass(frozen=True)
class RecordedRequest:
    """One real `urllib.request.Request`, as it went to the wire."""

    method: str
    url: str
    headers: Dict[str, str]
    authorization_present: bool
    body_bytes: Optional[bytes]
    body: Optional[Any]


@dataclass
class _Queued:
    method: str
    endpoint: str
    status: int = 200
    body: Optional[Dict[str, Any]] = None
    raw: Optional[bytes] = None
    http_error: bool = False


@dataclass
class _Response:
    """The minimal context manager `_request` consumes.

    Only `.read()` is touched by `wix_ecom._request` (`urlopen` at `:104`, `.read()` at `:105`).
    `.status` and `.headers` are provided so a future assertion about a response code has
    somewhere to read it from, not because anything consumes them today.
    """

    payload: bytes
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False


class WixTransport:
    """Replaces urllib.request.urlopen. Records the REAL request; serves queued responses.

    The queue is TYPED by the call each entry answers, and that is what makes "one create, not
    two" enforceable. An untyped FIFO of responses cannot do it: a regression that issues a
    second `POST .../gift-cards` instead of a query would pop the queued query response, parse
    it happily, and the queue would never be empty - so the named enforcement would not fire
    while the adapter created two cards.
    """

    def __init__(self) -> None:
        self.requests: List[RecordedRequest] = []
        self.timeouts: List[Any] = []
        self._queue: List[_Queued] = []

    # -- queueing ---------------------------------------------------------
    def expect(self, *, method: str, endpoint: str, status: int = 200,
               body: Optional[Dict[str, Any]] = None,
               raw: Optional[bytes] = None) -> "WixTransport":
        """Queue one response for one specific call. `endpoint` is a PATH.

        The stub prepends `wix_ecom.WIX_API_BASE` itself, so a test cannot accidentally pin a
        different host and still match.
        """
        self._queue.append(_Queued(method=method.upper(), endpoint=endpoint, status=status,
                                   body=body, raw=raw))
        return self

    def expect_http_error(self, *, method: str, endpoint: str, status: int) -> "WixTransport":
        """Queue a genuine `urllib.error.HTTPError`, so `_request`'s own reduction runs."""
        self._queue.append(_Queued(method=method.upper(), endpoint=endpoint, status=status,
                                   http_error=True))
        return self

    # -- the urlopen contract ---------------------------------------------
    def __call__(self, request: Any, timeout: Any = None) -> _Response:
        if not isinstance(request, urllib.request.Request):
            raise UnexpectedWixCall(
                f"the stub must not accept a bare URL - that would skip header and body "
                f"composition. Got {type(request).__name__}: {request!r}")
        self.timeouts.append(timeout)
        headers = dict(request.header_items())
        authorization_present = any(name.lower() == "authorization" for name in headers)
        headers = {name: ("<redacted>" if name.lower() == "authorization" else value)
                   for name, value in headers.items()}
        body_bytes = request.data
        try:
            parsed = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        except (ValueError, TypeError, UnicodeDecodeError):
            parsed = None
        self.requests.append(RecordedRequest(
            method=request.get_method(), url=request.full_url, headers=headers,
            authorization_present=authorization_present, body_bytes=body_bytes, body=parsed))

        if not self._queue:
            raise UnexpectedWixCall(
                f"no Wix call was expected here, got {request.get_method()} {request.full_url}")

        expected = self._queue[0]
        absolute = self._absolute(expected.endpoint)
        if (request.get_method(), request.full_url) != (expected.method, absolute):
            # Refused BEFORE the response is served, so the failure names the wrong call rather
            # than surfacing as a confusing parse error three lines later.
            raise UnexpectedWixCall(
                f"expected {expected.method} {expected.endpoint}, got "
                f"{request.get_method()} {request.full_url}")
        self._queue.pop(0)

        if expected.http_error:
            raise urllib.error.HTTPError(absolute, expected.status, "", {}, None)
        if expected.raw is not None:
            payload = expected.raw
        else:
            payload = json.dumps(expected.body if expected.body is not None else {}) \
                .encode("utf-8")
        return _Response(payload=payload, status=expected.status)

    # -- teardown ---------------------------------------------------------
    def assert_drained(self) -> None:
        """A call we asserted would happen and did not is the more dangerous direction."""
        if self._queue:
            unconsumed = [f"{entry.method} {entry.endpoint}" for entry in self._queue]
            raise UnexpectedWixCall(f"these expected Wix calls never happened: {unconsumed}")

    # -- reading the recording --------------------------------------------
    def count(self, *, method: str, endpoint: str) -> int:
        """How many recorded calls hit exactly this method and path.

        The named enforcement of "one create, not two": a direct count, independent of whether
        the typed queue happened to be drained.
        """
        absolute = self._absolute(endpoint)
        return sum(1 for recorded in self.requests
                   if (recorded.method, recorded.url) == (method.upper(), absolute))

    @staticmethod
    def _absolute(endpoint: str) -> str:
        from lambda_utils import wix_ecom

        return f"{wix_ecom.WIX_API_BASE}{endpoint}"


__all__ = ["RecordedRequest", "UnexpectedWixCall", "WixTransport"]
