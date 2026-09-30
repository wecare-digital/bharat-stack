"""Server-side authorisation for a customer session. The only correct way to trust a customer.

Why this must exist in the shared layer
---------------------------------------
Two facts together make every new customer route an IDOR waiting to happen.

**All 359 routes on the HTTP API report `AuthorizationType=NONE`** — measured live. There is no
gateway authorizer, so nothing rejects a request before it reaches a handler, and every check has
to happen in the handler.

**`lambda_utils.middleware.require_auth` is hardcoded to the STAFF pool.** A customer token passed
to it does not fail: `get_user` succeeds against the customer pool, the role lookup finds no staff
group, and the caller falls through to `Viewer`. So the obvious thing to reach for silently grants
a customer read access intended for staff. `secure-files` already discovered this and wrote its own
`_customer_identity` with an explicit issuer pin — but it lives *inside* that function, so every
other route would have to rediscover the same problem.

This module is that helper, promoted to the layer.

The three checks, and why each is load-bearing
----------------------------------------------
1. **The token is valid** — `GetUser` against Cognito. Proves it is live and unrevoked.
2. **The issuer is the CUSTOMER pool.** Step 1 alone does not do this: `GetUser` is called with
   only a token, and a *staff* token is also valid. Without the pin, a staff Viewer token would
   authorise as whichever customer the request claimed to be.
3. **The requested resource belongs to this customer.** Shape is not authorisation. A
   well-formed `CUS_...` from a request body proves only that the caller can type.

Never authorise on an identifier from the request
-------------------------------------------------
Not `customerId`, not `orderNumber`, not `paymentAttemptId`, not a receipt id. Those are all
things a customer legitimately knows about *their own* records and can therefore guess or
enumerate about somebody else's. Authority comes from the token, and the request identifier is
then checked against it — which is what `authorize_resource` is for.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

#: The customer pool. Deliberately NOT the staff pool `us-east-1_cSx0RHCIR`; keeping the two
#: apart is the whole point, and a single env var holding "the pool" is how they get confused.
CUSTOMER_POOL_ID = os.environ.get("CUSTOMER_POOL_ID", "us-east-1_46ULYuukt")
CUSTOMER_POOL_REGION = os.environ.get("AWS_REGION", "us-east-1")

#: The `iss` claim a customer token must carry.
CUSTOMER_POOL_ISSUER = (
    f"https://cognito-idp.{CUSTOMER_POOL_REGION}.amazonaws.com/{CUSTOMER_POOL_ID}"
)

_cognito = None


def _client():
    """Lazily built, so importing this module needs no AWS configuration."""
    global _cognito
    if _cognito is None:
        import boto3
        _cognito = boto3.client("cognito-idp", region_name=CUSTOMER_POOL_REGION)
    return _cognito


class CustomerNotAuthenticated(PermissionError):
    """No usable customer session on the request."""


class CustomerNotAuthorized(PermissionError):
    """Authenticated, but not for the resource requested.

    A distinct type from `CustomerNotAuthenticated` because the two must produce the same HTTP
    response body while being distinguishable in logs and metrics: a spike in this one is
    somebody probing other customers' records, and a spike in the other is a broken client.
    """


class CustomerIdentity:
    """A proven customer session."""

    __slots__ = ("customer_id", "phone", "subject")

    def __init__(self, *, customer_id: str, phone: str, subject: str) -> None:
        self.customer_id = customer_id
        self.phone = phone
        self.subject = subject

    def owns(self, customer_id: Optional[str]) -> bool:
        """Whether this session may act for `customer_id`. Exact match only."""
        return bool(customer_id) and customer_id == self.customer_id

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        # Never renders the phone number or the customer id: this lands in logs.
        return f"CustomerIdentity(subject=***{self.subject[-4:] if self.subject else ''})"


def bearer_token(event: Dict[str, Any]) -> str:
    """The bearer token from an API Gateway event, or ''.

    Header lookup is case-insensitive because HTTP headers are, and API Gateway v1 and v2 do not
    agree on casing — v2 lowercases, v1 preserves what the client sent. A case-sensitive read
    works in one and silently fails in the other.
    """
    headers = event.get("headers") or {}
    lowered = {str(k).lower(): v for k, v in headers.items()}
    raw = str(lowered.get("authorization") or "")
    if not raw:
        return ""
    parts = raw.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    # A bare token with no scheme. Accepted because clients get this wrong constantly and the
    # token is verified against Cognito either way, so leniency here costs nothing.
    return raw.strip()


def _unverified_issuer(token: str) -> str:
    """The `iss` claim, read WITHOUT signature verification.

    Safe only because it is used to *reject*, never to accept: the token has already been proven
    live by `GetUser`, and this narrows which pool proved it. Reading an unverified claim to
    grant anything would be the classic JWT mistake.
    """
    import base64
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload)).get("iss") or "")
    except Exception:  # noqa: BLE001 - a malformed token simply has no issuer
        return ""


def authenticate(event: Dict[str, Any]) -> CustomerIdentity:
    """Prove a customer session from the request, or raise `CustomerNotAuthenticated`.

    Order matters. `GetUser` runs first because it is the only step that proves the token is live
    and unrevoked; the issuer pin runs second to establish *which* pool vouched for it. Reversing
    them would let an expired customer token past the pin and into the handler.
    """
    token = bearer_token(event)
    if not token:
        raise CustomerNotAuthenticated("no bearer token on the request")

    try:
        user = _client().get_user(AccessToken=token)
    except Exception as error:  # noqa: BLE001
        # Type only. A Cognito error message can echo the token back.
        logger.info(
            '{"event":"customer_auth_rejected","reason":"%s"}', type(error).__name__
        )
        raise CustomerNotAuthenticated("token is not valid") from error

    issuer = _unverified_issuer(token)
    if issuer != CUSTOMER_POOL_ISSUER:
        # The check `require_auth` does not make. A staff token is *valid*, so without this it
        # would authorise as whichever customer the request named.
        logger.warning('{"event":"customer_auth_wrong_pool"}')
        raise CustomerNotAuthenticated("token was not issued by the customer pool")

    attributes = {a.get("Name"): a.get("Value")
                  for a in (user.get("UserAttributes") or [])}
    customer_id = str(attributes.get("custom:customer_id") or "")
    phone = str(attributes.get("phone_number") or user.get("Username") or "")

    if not customer_id:
        # The pool is phone-keyed, so a user can exist before a customer record does. That is a
        # half-provisioned account rather than an impostor, and it must not read as authorised
        # for anything — every downstream key is built from customerId.
        logger.warning('{"event":"customer_auth_no_customer_id"}')
        raise CustomerNotAuthenticated("session carries no customer id")

    return CustomerIdentity(
        customer_id=customer_id, phone=phone,
        subject=str(attributes.get("sub") or ""),
    )


def authorize_resource(identity: CustomerIdentity,
                       resource: Optional[Dict[str, Any]],
                       *, owner_field: str = "customerId") -> Dict[str, Any]:
    """Return `resource` if this session owns it, else raise `CustomerNotAuthorized`.

    A missing resource and a resource belonging to somebody else raise the *same* exception, so
    the caller cannot accidentally turn the endpoint into an existence oracle — "not found" and
    "not yours" must be indistinguishable to the client, or an attacker can enumerate which
    order numbers are real.
    """
    if not resource:
        raise CustomerNotAuthorized("resource does not exist or is not yours")
    if not identity.owns(str(resource.get(owner_field) or "")):
        logger.warning('{"event":"customer_idor_attempt","ownerField":"%s"}', owner_field)
        raise CustomerNotAuthorized("resource does not exist or is not yours")
    return dict(resource)


def require_customer(event: Dict[str, Any]) -> Tuple[Optional[CustomerIdentity],
                                                     Optional[Dict[str, Any]]]:
    """`(identity, None)` when authorised, `(None, response)` when not.

    Mirrors `middleware.require_auth`'s shape so a handler reads the same either way::

        identity, denied = customer_auth.require_customer(event)
        if denied:
            return denied

    Both failure modes return **401 with an identical body**. Not 403 for authorisation: a 403
    confirms the resource exists, and the whole point of `authorize_resource` collapsing the two
    cases is that it should not.
    """
    from lambda_utils.response import cors_response, extract_origin

    origin = extract_origin(event)
    try:
        return authenticate(event), None
    except CustomerNotAuthenticated:
        return None, cors_response(
            401, {"error": "VERIFICATION_REQUIRED",
                  "message": "Please verify your WhatsApp number to continue."}, origin)


def denied_response(event: Dict[str, Any]) -> Dict[str, Any]:
    """The 401 to return for a `CustomerNotAuthorized`, identical to the unauthenticated one."""
    from lambda_utils.response import cors_response, extract_origin
    return cors_response(
        401, {"error": "VERIFICATION_REQUIRED",
              "message": "Please verify your WhatsApp number to continue."},
        extract_origin(event))


__all__ = [
    "CUSTOMER_POOL_ID",
    "CUSTOMER_POOL_ISSUER",
    "CustomerNotAuthenticated",
    "CustomerNotAuthorized",
    "CustomerIdentity",
    "bearer_token",
    "authenticate",
    "authorize_resource",
    "require_customer",
    "denied_response",
]
