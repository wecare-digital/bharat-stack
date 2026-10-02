"""Wix Service Plugin request verification. The raw request BODY is the JWT.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
section 5 (DECISION 4), 5.1 (the ordered checks), 5.1.1 (the library and its layer) and 5.2 (why the
route carries no API Gateway authorizer).

The envelope, measured rather than assumed
------------------------------------------
    <JWT payload>
      data
        request   : GetBalanceRequest | RedeemRequest | VoidRequest
        metadata  : wix.common.spi.Context
      aud  : our appId
      iss  : "wix.com"
      iat  : int
      exp  : int

Both halves are under `data`. Revision 1 of the design placed `request` at the token root and
attributed that shape to a component that does not exist in the fetched service schema, so a
verifier written to it would have read `None` on every live call. Test 5 pins the correction.

The body IS the token
---------------------
Wix's own introduction example is a `POST` whose `-d` argument is a bare `eyJ...`. So the signature
is `verify(raw_body, ...)` - body first, because the body is the token. An `Authorization` header is
IGNORED ENTIRELY, and test 4 presents a valid JWT there with a non-JWT body and asserts a rejection,
so the ambiguity cannot be reintroduced by a later "helpful" fallback.

NO Content-Type BRANCH, and that is a decision (MEDIUM-4)
---------------------------------------------------------
Revision 2 rejected any request whose `Content-Type` was not one of three values. That is dropped.
The only documented `plain/text` example is the app-install instance-id callback, not a gift-card
call, and Wix publishes no Content-Type contract for the three gift-card methods at all. 401-ing
every live request on an undocumented header value is FEATURE-DEAD rather than fail-closed: the
plugin would answer nothing and the symptom would be indistinguishable from a bad key.

The real discriminator is the body: three base64url segments separated by dots, checked before any
claim is decoded. That is a property of the token rather than a declaration about it, and it refuses
exactly the same garbage under every declared type. `headers` remains a parameter and is
deliberately unused for any decision - a test asserts this module never reads `content-type`.

Verification is FIRST and FAIL-CLOSED at every step
---------------------------------------------------
Every failure raises `SpiUnauthorized`, which the handler answers as **401 with an EMPTY body**. No
error detail, because the caller is either Wix (which does not need it) or an attacker (who must not
get it).

The algorithm allowlist is `{RS256, RS384, RS512}`. `alg: none` and every HMAC algorithm are refused
outright: accepting the token's own `alg` is the classic JWT key-confusion attack, and an HMAC `alg`
with an RSA public key as the secret is its textbook form. Wix does not name the exact algorithm on
any fetched page, so the three-member allowlist is the fail-closed position until it is read once
from a real token at registration time.

The library, and why not PyJWT
------------------------------
Python's standard library cannot verify an RSA signature, so `cryptography` does it - the layer
`arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1`, which this account already
attaches to `wecare-whatsapp-business-api` for its own RSA work. PyJWT with `[crypto]` would depend
on `cryptography` underneath anyway, so it buys a convenience API at the cost of a second packaged
dependency, a second version to pin and a new layer to maintain. `base64` and `json` are stdlib and
are used on the ENCODED segments only; the signature check itself is `public_key.verify(...)`, never
a comparison written here.

`scripts/provision_gift_cards_roles.py` attaches that layer, pinned to version 1, and
`tests/test_gift_cards_iam_and_table.py` test 110 resolves this module's imports against the
declared layer set so the deploy gate is not the first place a missing layer is discovered.

The public key is read LAZILY, per request
------------------------------------------
Through an INJECTED reader, called inside `verify`. A module-scope read caches for the life of the
execution environment, so a key rotation would not take effect until every warm sandbox recycled -
the exact defect fixed in `payments/razorpay-webhook` on 2026-09-19. Neither the key nor the pepper
appears in any logging expression, not even reduced to a bool: CodeQL's
`py/clear-text-logging-sensitive-data` tracks taint across function boundaries and has already
failed this build twice over a ternary on a key's truthiness. This module logs nothing at all.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

#: GUARDED, and the guard is a PACKAGING fact rather than a doubt about the dependency.
#:
#: `cryptography` lives in a layer attached to `wecare-wix-giftcard-spi` alone, but this file is part
#: of the shared `lambda_utils` tree, so `scripts/deploy_all_lambdas.py` packages it into every
#: function that ships that tree - including `wecare-checkout`, which has no layers and never calls
#: anything here. An unguarded top-level import would therefore fail that script's static import
#: check for ~60 unrelated functions, which `tests/test_checkout_package_completeness.py` enforces
#: as an error.
#:
#: The import stays at module scope rather than moving inside `verify`, deliberately: the deploy
#: gate reads top-level imports, so moving it would make the missing-layer case INVISIBLE to
#: tooling. Guarding downgrades it from an error to a warning there, and
#: `tests/test_gift_cards_iam_and_table.py` test 110 is what keeps it an error for the one function
#: that needs it - resolving these imports against the DECLARED layer set offline.
#:
#: The failure mode is FAIL CLOSED: without the layer `verify` refuses every request rather than
#: skipping the signature check. A verifier that could not verify must answer 401, not 200.
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
except ImportError as _import_error:          # pragma: no cover - only without the layer
    _CRYPTOGRAPHY_UNAVAILABLE = type(_import_error).__name__
    InvalidSignature = None   # type: ignore[assignment]
    hashes = None             # type: ignore[assignment]
    padding = None            # type: ignore[assignment]
    load_pem_public_key = None  # type: ignore[assignment]
else:
    _CRYPTOGRAPHY_UNAVAILABLE = ""

#: Secret NAME, never a value. Carries `public_key`, `app_id`, `instance_id` and `code_pepper`.
SECRET_ID = "wecare/wix/giftcard-spi"
PUBLIC_KEY_FIELD = "public_key"
APP_ID_FIELD = "app_id"
INSTANCE_ID_FIELD = "instance_id"

#: Asymmetric only. The key is an app PUBLIC key from the Wix dashboard, so an HMAC algorithm here
#: would mean verifying a signature with a value the attacker also has.
#:
#: Mapped to hash NAMES rather than to `hashes.SHA256` directly, so this module still IMPORTS when
#: the layer is absent (see the guarded import above). The class is resolved per call by
#: `_hash_for`, after `verify` has already refused on `_CRYPTOGRAPHY_UNAVAILABLE`.
ALLOWED_ALGORITHMS: Dict[str, str] = {
    "RS256": "SHA256",
    "RS384": "SHA384",
    "RS512": "SHA512",
}

#: Bounded and symmetric. A missing `iat` or `exp` is REJECTED, never defaulted.
CLOCK_SKEW_SECONDS = 60

ISSUER = "wix.com"

IDENTITY_TYPES = ("ANONYMOUS_VISITOR", "MEMBER", "WIX_USER", "APP")

_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


class SpiUnauthorized(Exception):
    """Verification failed. The handler answers 401 with an EMPTY body.

    The message is for OUR logs and is built from known-safe parts only - never a claim value,
    never a key, never a segment of the token.
    """


@dataclass(frozen=True)
class Context:
    """`wix.common.spi.Context`, the envelope metadata at `data.metadata`.

    `requestId` is Wix's own offer for log correlation - "You may print this ID to your logs to
    help with future debugging and easier correlation with Wix's logs" - which is why no masked
    guessing is needed on this path and why the gift-card code never has to appear in a log.
    """

    request_id: str = ""
    currency: str = ""
    instance_id: str = ""
    identity: Dict[str, Any] = field(default_factory=dict)
    languages: Tuple[str, ...] = ()

    @property
    def identity_type(self) -> str:
        return str(self.identity.get("identityType") or "")


@dataclass(frozen=True)
class Verified:
    """What a verified call yields: the SPI request object and its envelope context.

    Both, not one. Section 5.1 step 6 requires `data.metadata` parsed as a `Context` AND
    `data.request` handed to the method handler, so returning only the Context would discard the
    request and returning only the request would discard `requestId` and `instanceId`.
    """

    request: Dict[str, Any]
    context: Context


SecretReader = Callable[[str], Mapping[str, Any]]


def _hash_for(algorithm: str):
    """The hash instance the `alg` names, resolved from the allowlist and never from the token.

    The token supplies a NAME that must already be in `ALLOWED_ALGORITHMS`; the class comes from
    the library. That is what makes "the token cannot choose its own algorithm" structural.
    """
    return getattr(hashes, ALLOWED_ALGORITHMS[algorithm])()


def _b64url(segment: str) -> bytes:
    """Decode one base64url segment, padding it ourselves. Raises `SpiUnauthorized` on garbage."""
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError) as error:
        raise SpiUnauthorized("a token segment is not base64url") from error


def _json(raw: bytes) -> Any:
    """Parse a decoded segment with `parse_float=Decimal`.

    MANDATORY, not optional. The SPI sends amounts as JSON NUMBERS (`"amount": 50.00`), and
    `json.loads` produces a `float` for `12.34` by default - which would put a float on the payment
    path before a single line of our own logic ran. A float must never be constructed, not even
    transiently.
    """
    try:
        return json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, ValueError) as error:
        raise SpiUnauthorized("a token segment is not JSON") from error


def token_from_body(raw_body: Any, *, is_base64_encoded: bool = False) -> str:
    """The JWT, from the raw request body. `isBase64Encoded` is honoured FIRST.

    Before any JWT parsing, because a binary-media-type route would otherwise present a
    double-encoded token and the three-segment check would refuse a perfectly good call.
    """
    if isinstance(raw_body, bytes):
        text = raw_body.decode("utf-8", errors="replace")
    elif isinstance(raw_body, str):
        text = raw_body
    else:
        raise SpiUnauthorized("the request body is not a string")
    if is_base64_encoded:
        try:
            text = base64.b64decode(text, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as error:
            raise SpiUnauthorized("the body is flagged base64 and is not") from error
    return text.strip()


def is_jwt_shaped(token: Any) -> bool:
    """Three non-empty base64url segments separated by dots. THE discriminator.

    A property of the token rather than a declaration about it, which is why it replaces the
    Content-Type check rather than sitting beside it.
    """
    if not isinstance(token, str):
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(part and _SEGMENT.match(part) for part in parts)


def verify(raw_body: Any, *, headers: Optional[Mapping[str, Any]] = None, now: int,
           reader: SecretReader, is_base64_encoded: bool = False,
           secret_id: str = SECRET_ID) -> Verified:
    """Verify a Wix Service Plugin request and return its `request` plus its `Context`.

    The order is section 5.1's and every step fails closed:

    1. honour `isBase64Encoded`, then refuse a body that is not three base64url segments, BEFORE
       any claim is decoded;
    2. verify the signature with the app's PUBLIC key, read by reference and LAZILY;
    3. `aud == <our Wix application id>`, absent or multi-valued refused rather than coerced;
    4. `iss == "wix.com"`, exact string;
    5. `iat <= now + 60` and `exp > now - 60`, a missing claim refused and never defaulted;
    6. only then `data.metadata` as a `Context`, `metadata.instanceId` against the installed
       instance, and `data.request` returned.

    `headers` is accepted and used for NO decision. It is in the signature because the documented
    call shape carries headers and a later reader will look for them; it is unused because the
    Content-Type rejection was dropped and `Authorization` is ignored entirely.
    """
    if _CRYPTOGRAPHY_UNAVAILABLE:
        # FAIL CLOSED. Without the layer no signature can be checked, and a verifier that cannot
        # verify must answer 401 rather than wave the request through.
        raise SpiUnauthorized(
            f"the signature library is unavailable ({_CRYPTOGRAPHY_UNAVAILABLE}); "
            "the cryptography layer is not attached to this function")
    token = token_from_body(raw_body, is_base64_encoded=is_base64_encoded)
    if not is_jwt_shaped(token):
        raise SpiUnauthorized("the request body is not a three-segment JWT")
    header_segment, payload_segment, signature_segment = token.split(".")

    header = _json(_b64url(header_segment))
    if not isinstance(header, dict):
        raise SpiUnauthorized("the token header is not an object")
    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in ALLOWED_ALGORITHMS:
        # Covers `none` and every HMAC algorithm in one refusal: the allowlist is the decision,
        # and the token does not get to choose.
        raise SpiUnauthorized("the token names an algorithm outside the allowlist")

    # Read at THIS point, per request, not at import.
    secret = reader(secret_id) or {}
    public_key_pem = secret.get(PUBLIC_KEY_FIELD)
    app_id = secret.get(APP_ID_FIELD)
    instance_id = secret.get(INSTANCE_ID_FIELD)
    if not isinstance(public_key_pem, str) or not public_key_pem:
        raise SpiUnauthorized("no usable public key is configured")
    if not isinstance(app_id, str) or not app_id:
        raise SpiUnauthorized("no application id is configured")
    if not isinstance(instance_id, str) or not instance_id:
        raise SpiUnauthorized("no installed instance id is configured")

    try:
        public_key = load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as error:  # noqa: BLE001 - any failure here is a refusal, never a 500
        raise SpiUnauthorized(
            f"the configured public key did not load ({type(error).__name__})") from None

    signing_input = (header_segment + "." + payload_segment).encode("ascii")
    try:
        public_key.verify(_b64url(signature_segment), signing_input,
                          padding.PKCS1v15(), _hash_for(algorithm))
    except InvalidSignature:
        raise SpiUnauthorized("the token signature does not verify") from None
    except Exception as error:  # noqa: BLE001 - e.g. an EC key presented for an RS alg
        raise SpiUnauthorized(
            f"the token signature could not be checked ({type(error).__name__})") from None

    claims = _json(_b64url(payload_segment))
    if not isinstance(claims, dict):
        raise SpiUnauthorized("the token payload is not an object")

    audience = claims.get("aud")
    if isinstance(audience, (list, tuple, set)):
        # Refused rather than searched. A multi-valued `aud` means the token was minted for more
        # than one consumer, and accepting it because our id is somewhere in the list is how a
        # token issued for a different app gets honoured here.
        raise SpiUnauthorized("a multi-valued aud is refused")
    if not isinstance(audience, str) or audience != app_id:
        raise SpiUnauthorized("aud is not this application")
    if claims.get("iss") != ISSUER:
        raise SpiUnauthorized("iss is not wix.com")

    issued_at = _timestamp(claims.get("iat"), "iat")
    expires_at = _timestamp(claims.get("exp"), "exp")
    moment = int(now)
    if issued_at > moment + CLOCK_SKEW_SECONDS:
        raise SpiUnauthorized("iat is in the future beyond the permitted skew")
    if expires_at <= moment - CLOCK_SKEW_SECONDS:
        raise SpiUnauthorized("exp is in the past beyond the permitted skew")

    data = claims.get("data")
    if not isinstance(data, dict):
        # Pins revision 1's envelope correction: a payload with `request` at the ROOT and nothing
        # under `data` is refused rather than silently read as an empty request.
        raise SpiUnauthorized("the token carries no data object")
    request = data.get("request")
    if not isinstance(request, dict):
        raise SpiUnauthorized("data.request is not an object")
    context = _context(data.get("metadata"))
    if context.instance_id != instance_id:
        raise SpiUnauthorized("the instanceId is not the installed instance")
    return Verified(request=dict(request), context=context)


def _timestamp(value: Any, name: str) -> int:
    """An integer epoch-second claim, REJECTED when absent rather than defaulted."""
    if value is None or isinstance(value, bool):
        raise SpiUnauthorized(f"{name} is missing")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise SpiUnauthorized(f"{name} is not an integer")
        return int(value)
    if isinstance(value, int):
        return value
    raise SpiUnauthorized(f"{name} is not an integer")


def _context(metadata: Any) -> Context:
    """`data.metadata` as a `wix.common.spi.Context`.

    A `StringValue`-wrapped field is accepted in either form (`{"value": "x"}` or `"x"`), because
    the service schema types several of these as `StringValue` while the REST guide's prose shows
    them flat, and refusing one spelling would reject live traffic over a documentation
    inconsistency rather than over anything security-relevant.
    """
    if not isinstance(metadata, dict):
        raise SpiUnauthorized("data.metadata is not an object")
    languages = metadata.get("languages")
    return Context(
        request_id=_string_value(metadata.get("requestId")),
        currency=_string_value(metadata.get("currency")),
        instance_id=_string_value(metadata.get("instanceId")),
        identity=dict(metadata.get("identity") or {}),
        languages=tuple(str(item) for item in languages) if isinstance(languages, list) else (),
    )


def _string_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value)


__all__ = [
    "ALLOWED_ALGORITHMS", "APP_ID_FIELD", "CLOCK_SKEW_SECONDS", "Context", "IDENTITY_TYPES",
    "INSTANCE_ID_FIELD", "ISSUER", "PUBLIC_KEY_FIELD", "SECRET_ID", "SpiUnauthorized", "Verified",
    "is_jwt_shaped", "token_from_body", "verify",
]
