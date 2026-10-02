"""Wix Service Plugin JWT verification, with a real RSA keypair generated in the fixture.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
section 5 (DECISION 4), 5.1 (the ordered checks) and 5.1.1 (the library), and the test list in
section 9.1 (tests 1-21).

A real keypair, not a mock. The whole of this module's value is that a signature verifies or does
not, and a fake that returns what it is told proves nothing about that. `cryptography` signs here
with the same primitives the verifier checks with, so an `alg` confusion or a wrong-key test is a
genuine cryptographic refusal rather than an assertion about a stub.

TWO TESTS ARE RE-POINTED, AND BOTH REASONS ARE MEASURED
-------------------------------------------------------
* Test 2 was `test_a_content_type_that_is_not_jwt_or_text_is_refused`. MEDIUM-4 drops the
  Content-Type rejection entirely, so that test would pin a behaviour the design removed. It is
  renamed to `test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type` and
  PARAMETRISED over `application/json`, `application/jwt`, `text/plain`, `plain/text` and a missing
  header, asserting the declared type never decides the outcome. The reason the rejection went:
  Wix publishes no Content-Type contract for the three gift-card methods, the only documented
  `plain/text` example is the app-install instance-id callback, and 401-ing every live call on an
  undocumented header value is feature-dead rather than fail-closed.
* Test 13's two names are PREFIXED (`..._spi_token_...`), because
  `tests/test_customer_auth_and_throttle.py:92` already owns the unprefixed
  `test_an_expired_token_is_refused` for a Cognito token, and two identically named failures in one
  report are ambiguous about which auth path broke.

Test 4 is kept exactly as the design has it: a valid JWT in an `Authorization` header with a
non-JWT body is REFUSED, so a later "helpful" header fallback cannot be added without this failing.
"""

from __future__ import annotations

import ast
import base64
import json
import pathlib
import sys
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))

from lambda_utils.ecommerce import gift_card_spi_auth as auth  # noqa: E402

MODULE = ROOT / "amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py"
SOURCE = MODULE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE, filename=str(MODULE))
FIXTURES = ROOT / "tests" / "fixtures"

#: Matches the three fixtures. Not credentials - a Wix application id and an installed instance id
#: are both public identifiers, and the fixtures are transcriptions of a documented envelope.
APP_ID = "11111111-2222-4333-8444-555555555555"
INSTANCE_ID = "99999999-8888-4777-8666-555555555555"

NOW = 1_700_000_000

CONTENT_TYPES = ["application/json", "application/jwt", "text/plain", "plain/text", None]


def load(name: str) -> dict:
    payload = json.loads((FIXTURES / f"wix_spi_{name}_jwt_payload.json").read_text(
        encoding="utf-8"))
    payload.pop("_fixture", None)
    return payload


@pytest.fixture(scope="module")
def keys():
    """One RSA keypair for the whole module, and a second one to be the WRONG key.

    2048 bits: large enough to be a real RS256 key and small enough that generating two of them is
    not the slowest thing in the suite.
    """
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "private": private,
        "other": other,
        "public_pem": private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii"),
        "other_public_pem": other.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii"),
    }


def _segment(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unsigned(header: dict, payload: dict) -> str:
    return (_segment(json.dumps(header).encode("utf-8")) + "."
            + _segment(json.dumps(payload).encode("utf-8")))


def sign(keys, payload: dict, *, alg: str = "RS256", key=None, header_extra=None) -> str:
    """A genuinely signed JWT. The hash follows the `alg` the header names."""
    header = {"alg": alg, "typ": "JWT"}
    header.update(header_extra or {})
    signing_input = _unsigned(header, payload)
    algorithm = {"RS256": hashes.SHA256, "RS384": hashes.SHA384,
                 "RS512": hashes.SHA512}[alg]()
    signature = (key or keys["private"]).sign(signing_input.encode("ascii"),
                                              padding.PKCS1v15(), algorithm)
    return signing_input + "." + _segment(signature)


def reader_for(keys, *, public_pem=None, app_id=APP_ID, instance_id=INSTANCE_ID, calls=None):
    """An injected secret reader. Records each call so laziness is observable."""
    def read(secret_id):
        if calls is not None:
            calls.append(secret_id)
        # `is not None`, not `or`: an EMPTY configured key is one of the cases under test, and an
        # `or` fallback would silently substitute the real one and pass.
        return {auth.PUBLIC_KEY_FIELD:
                public_pem if public_pem is not None else keys["public_pem"],
                auth.APP_ID_FIELD: app_id,
                auth.INSTANCE_ID_FIELD: instance_id}
    return read


def verify(keys, token, *, now=NOW, headers=None, is_base64_encoded=False, **reader_kwargs):
    return auth.verify(token, headers=headers or {}, now=now,
                       reader=reader_for(keys, **reader_kwargs),
                       is_base64_encoded=is_base64_encoded)


# ── 1 / 2: the body is the token, and the shape is the discriminator ───────────

def test_a_body_that_is_not_a_jwt_is_refused(keys):
    """401 with an empty body, raised before anything is decoded."""
    for body in ("", "   ", "not-a-token", "only.two", "a.b.c.d", "a..c", None, 7, b"\xff\xfe",
                 json.dumps({"request": {"code": "WDGC0000TEST0001"}})):
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, body)


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type(keys,
                                                                               content_type):
    """MEDIUM-4. The declared type NEVER decides the outcome, in either direction.

    A JSON body is refused under `application/jwt`, and a perfectly good token is ACCEPTED under
    `application/json`. Both halves matter: the first is the fail-closed property, and the second is
    the one revision 2 got wrong - rejecting on an undocumented header value would have 401-ed every
    live call, which is feature-dead rather than safe.
    """
    headers = {} if content_type is None else {"content-type": content_type}
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, json.dumps({"data": {"request": {}}}), headers=headers)

    good = sign(keys, load("get_balance"))
    verified = verify(keys, good, headers=headers)
    assert verified.request["code"] == "WDGC0000TEST0001"


def test_the_verifier_never_reads_the_content_type_header_at_all():
    """The structural form of MEDIUM-4, over the AST.

    `headers` is in the signature because the documented call shape carries headers and a later
    reader will look for them. It must contribute to no decision, so a test that only tried a few
    header values could pass on code that branched on a fifth.
    """
    for forbidden in ("content-type", "Content-Type", "content_type", "CONTENT_TYPE",
                      "authorization", "Authorization"):
        offenders = [node.lineno for node in ast.walk(TREE)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)
                     and node.value == forbidden]
        assert not offenders, f"line {offenders}: the verifier reads {forbidden}"
    verify_fn = next(node for node in ast.walk(TREE)
                     if isinstance(node, ast.FunctionDef) and node.name == "verify")
    body = ast.unparse(verify_fn)
    assert "headers" in body, "headers must stay in the signature"
    assert "headers[" not in body and "headers.get" not in body, (
        "headers is being read, so it can decide something")


def test_a_base64_encoded_api_gateway_body_is_decoded_before_parsing(keys):
    """`isBase64Encoded: True`. Honoured FIRST, because a binary-media-type route would otherwise
    present a double-encoded token and the three-segment check would refuse a good call."""
    token = sign(keys, load("get_balance"))
    wrapped = base64.b64encode(token.encode("ascii")).decode("ascii")

    verified = verify(keys, wrapped, is_base64_encoded=True)
    assert verified.request["code"] == "WDGC0000TEST0001"
    # And the flag is honoured rather than guessed: the same body without it is refused.
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, wrapped, is_base64_encoded=False)
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, "not base64 at all", is_base64_encoded=True)


def test_a_jwt_in_an_authorization_header_with_a_non_jwt_body_is_refused(keys):
    """MEDIUM-18. The body is the ONLY token source.

    Wix's own introduction example is a POST whose `-d` argument is a bare `eyJ...`, so the header
    is not a fallback. This test exists so a later "helpful" fallback cannot be added quietly.
    """
    token = sign(keys, load("get_balance"))
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, "{}", headers={"authorization": f"Bearer {token}"})
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, "", headers={"Authorization": token})


# ── 5 / 6: the envelope ───────────────────────────────────────────────────────

def test_the_spi_request_object_is_read_from_data_request(keys):
    """Pins revision 1's envelope correction. A payload with `request` at the ROOT and nothing under
    `data` is refused - a verifier written to the wrong shape would have read `None` on every live
    call and answered as though the request were empty."""
    root_shaped = {"request": {"code": "WDGC0000TEST0001"}, "metadata": {},
                   "aud": APP_ID, "iss": "wix.com", "iat": NOW, "exp": NOW + 600}
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, root_shaped))

    nested = load("get_balance")
    assert verify(keys, sign(keys, nested)).request == nested["data"]["request"]


def test_the_metadata_is_read_from_data_metadata_as_a_context(keys):
    """`wix.common.spi.Context`, with `StringValue`-wrapped fields unwrapped.

    Either spelling is accepted, because the service schema types several of these as `StringValue`
    while the REST guide's prose shows them flat - and refusing one spelling would reject live
    traffic over a documentation inconsistency rather than over anything security-relevant.
    """
    verified = verify(keys, sign(keys, load("get_balance")))
    context = verified.context
    assert isinstance(context, auth.Context)
    assert context.request_id == "a1b2c3d4-0000-4000-8000-0000000000rq"
    assert context.currency == "INR"
    assert context.instance_id == INSTANCE_ID
    assert context.identity_type == "ANONYMOUS_VISITOR"
    assert context.languages == ("en-US",)
    assert context.identity_type in auth.IDENTITY_TYPES

    flat = load("get_balance")
    flat["data"]["metadata"] = {"requestId": "plain-request-id", "currency": "INR",
                               "instanceId": INSTANCE_ID, "identity": {"identityType": "APP"},
                               "languages": ["en-US"]}
    assert verify(keys, sign(keys, flat)).context.request_id == "plain-request-id"

    missing = load("get_balance")
    missing["data"].pop("metadata")
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, missing))


# ── 7-10: the signature and the algorithm ─────────────────────────────────────

def test_a_signature_from_the_wrong_key_is_refused(keys):
    """A genuine cryptographic refusal: signed with one key, verified against another."""
    token = sign(keys, load("get_balance"), key=keys["other"])
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, token)
    # And the same token verifies against its OWN key, so the refusal is about the key and not
    # about the token being malformed.
    assert verify(keys, token, public_pem=keys["other_public_pem"]).request


def test_a_tampered_payload_is_refused(keys):
    """The signature covers `header.payload`, so editing one claim invalidates it."""
    token = sign(keys, load("get_balance"))
    header_segment, payload_segment, signature = token.split(".")
    tampered = load("get_balance")
    tampered["aud"] = "a-different-app"
    forged = header_segment + "." + _segment(json.dumps(tampered).encode("utf-8")) + "." \
        + signature
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, forged)


def test_alg_none_is_refused(keys):
    """The classic confusion attack: an unsigned token presenting itself as valid."""
    payload = load("get_balance")
    unsigned = _unsigned({"alg": "none", "typ": "JWT"}, payload) + "."
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, unsigned)
    # Also with a junk signature segment, so the refusal is on the `alg` and not on the shape.
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, _unsigned({"alg": "none"}, payload) + "." + _segment(b"ignored"))
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, _unsigned({"alg": "NONE"}, payload) + "." + _segment(b"ignored"))


def test_an_hmac_alg_with_the_public_key_as_secret_is_refused(keys):
    """The key-confusion form, and the textbook one: the PUBLIC key is not secret, so an HMAC
    signed with it is forgeable by anyone who can read the app dashboard."""
    import hmac as _hmac
    from hashlib import sha256

    payload = load("get_balance")
    for alg in ("HS256", "HS384", "HS512"):
        signing_input = _unsigned({"alg": alg, "typ": "JWT"}, payload)
        mac = _hmac.new(keys["public_pem"].encode("ascii"), signing_input.encode("ascii"),
                        sha256).digest()
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, signing_input + "." + _segment(mac))


def test_the_token_cannot_choose_its_own_algorithm(keys):
    """Only RS256, RS384 and RS512. The allowlist is the decision, not the header.

    Wix does not name the exact algorithm on any fetched page, so the three-member allowlist is the
    fail-closed position until it is read once from a real token at registration time.
    """
    assert set(auth.ALLOWED_ALGORITHMS) == {"RS256", "RS384", "RS512"}
    for alg in auth.ALLOWED_ALGORITHMS:
        assert verify(keys, sign(keys, load("get_balance"), alg=alg)).request

    payload = load("get_balance")
    for refused in ("ES256", "PS256", "RSA-OAEP", "rs256", "", "RS128"):
        token = _unsigned({"alg": refused, "typ": "JWT"}, payload) + "." + _segment(b"x")
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, token)
    # A non-string `alg` too, so a JSON `null` or a number cannot slip past a membership test.
    for refused in (None, 256, True, ["RS256"]):
        token = _unsigned({"alg": refused, "typ": "JWT"}, payload) + "." + _segment(b"x")
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, token)


def test_a_missing_cryptography_layer_refuses_every_request_rather_than_skipping_the_check(
        keys, monkeypatch):
    """The guarded import fails CLOSED, and the guard is a PACKAGING fact rather than a doubt.

    This module is part of the shared `lambda_utils` tree, so `deploy_all_lambdas.py` packages it
    into every function that ships that tree - including `wecare-checkout`, which has no layers and
    never calls anything here. An unguarded top-level import would fail that script's static import
    check for ~60 unrelated functions, which `tests/test_checkout_package_completeness.py` enforces
    as an error.

    The import stays at MODULE scope rather than moving inside `verify`, deliberately: the deploy
    gate reads top-level imports, so moving it would make a missing layer invisible to tooling.
    Guarding downgrades it to a warning there, and test 110 in
    `tests/test_gift_cards_iam_and_table.py` keeps it an error for the one function that needs it.

    What must never happen is the third option: importing optionally and then verifying nothing.
    """
    token = sign(keys, load("get_balance"))
    assert verify(keys, token).request, "the real path must work, or this test proves nothing"

    monkeypatch.setattr(auth, "_CRYPTOGRAPHY_UNAVAILABLE", "ModuleNotFoundError")
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, token)

    # The refusal is the FIRST thing checked, so a missing layer cannot be distinguished from a bad
    # token by how far the request got.
    verify_fn = next(node for node in ast.walk(TREE)
                     if isinstance(node, ast.FunctionDef) and node.name == "verify")
    first = ast.unparse(verify_fn.body[1] if isinstance(verify_fn.body[0], ast.Expr)
                        else verify_fn.body[0])
    assert "_CRYPTOGRAPHY_UNAVAILABLE" in first

    # And the allowlist holds hash NAMES, so the module still imports without the layer.
    assert set(auth.ALLOWED_ALGORITHMS.values()) == {"SHA256", "SHA384", "SHA512"}
    assert all(isinstance(value, str) for value in auth.ALLOWED_ALGORITHMS.values())


def test_the_signature_check_is_the_librarys_and_not_one_we_wrote():
    """`public_key.verify(...)`, never a comparison in this module.

    Python's standard library cannot verify an RSA signature, which is the sentence revision 2's
    "a standard library does the parsing" elided. `base64` and `json` are stdlib and are used on
    the ENCODED segments only.
    """
    assert "load_pem_public_key" in SOURCE
    assert "InvalidSignature" in SOURCE
    assert "PKCS1v15" in SOURCE
    verify_fn = next(node for node in ast.walk(TREE)
                     if isinstance(node, ast.FunctionDef) and node.name == "verify")
    rendered = ast.unparse(verify_fn)
    assert "public_key.verify(" in rendered
    assert "compare_digest" not in rendered, "a hand-rolled signature comparison"
    assert "hmac" not in rendered.lower()


# ── 11 / 12: aud and iss ──────────────────────────────────────────────────────

def test_an_aud_that_is_not_our_app_id_is_refused(keys):
    """Compared explicitly against the CONFIGURED value, and a multi-valued `aud` is refused
    rather than searched: a token minted for more than one consumer must not be honoured here
    because our id happens to be in the list."""
    payload = load("get_balance")
    for bad in ("another-app", "", None, [APP_ID], [APP_ID, "another-app"], (APP_ID,),
                {"value": APP_ID}):
        broken = dict(payload)
        broken["aud"] = bad
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, sign(keys, broken))
    missing = dict(payload)
    missing.pop("aud")
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, missing))


def test_an_iss_other_than_wix_com_is_refused(keys):
    """Exact string. `www.wix.com` and `WIX.COM` are both refused."""
    assert auth.ISSUER == "wix.com"
    payload = load("get_balance")
    for bad in ("www.wix.com", "WIX.COM", "wix.com ", "", None, "wix.com.evil.example"):
        broken = dict(payload)
        broken["iss"] = bad
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, sign(keys, broken))


# ── 13 / 14: the time claims. Prefixed names; see the module docstring ─────────

def test_an_expired_spi_token_is_refused(keys):
    """Skew is bounded and symmetric at 60 seconds."""
    assert auth.CLOCK_SKEW_SECONDS == 60
    payload = load("get_balance")
    payload["exp"] = NOW - 61
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, payload))
    # Just inside the skew: accepted, so the bound is a bound and not a rounding.
    payload["exp"] = NOW - 59
    assert verify(keys, sign(keys, payload)).request


def test_an_spi_iat_in_the_future_is_refused(keys):
    payload = load("get_balance")
    payload["iat"] = NOW + 61
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, payload))
    payload["iat"] = NOW + 59
    assert verify(keys, sign(keys, payload)).request


def test_a_missing_iat_or_exp_is_refused_not_defaulted(keys):
    """Defaulting an absent `exp` to "now plus something" is how a replayed token lives forever."""
    for claim in ("iat", "exp"):
        payload = load("get_balance")
        payload.pop(claim)
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, sign(keys, payload))
        for bad in (None, "1700000000", True, 1.5, [NOW]):
            broken = load("get_balance")
            broken[claim] = bad
            with pytest.raises(auth.SpiUnauthorized):
                verify(keys, sign(keys, broken))


# ── 15: the installed instance ────────────────────────────────────────────────

def test_an_instance_id_that_is_not_the_installed_instance_is_refused(keys):
    """A valid Wix signature proves the caller is Wix. It does not prove the call is for OUR site -
    `metadata.instanceId` is what does that, and it is checked LAST, after everything cryptographic,
    so a wrong instance is not distinguishable from a bad signature by timing or by response."""
    payload = load("get_balance")
    payload["data"]["metadata"]["instanceId"] = {"value": "ee000000-0000-4000-8000-000000000bad"}
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, payload))

    payload["data"]["metadata"].pop("instanceId")
    with pytest.raises(auth.SpiUnauthorized):
        verify(keys, sign(keys, payload))


def test_an_unconfigured_key_app_id_or_instance_id_refuses_rather_than_failing_open(keys):
    """Fail closed on OUR OWN misconfiguration too. An empty configured `aud` compared against an
    empty claim would otherwise match."""
    token = sign(keys, load("get_balance"))
    for override in ({"public_pem": ""}, {"app_id": ""}, {"instance_id": ""},
                     {"public_pem": "-----BEGIN PUBLIC KEY-----\nnot a key\n"
                                    "-----END PUBLIC KEY-----\n"}):
        with pytest.raises(auth.SpiUnauthorized):
            verify(keys, token, **override)


# ── 19 / 20 / 21: the secret, the logs, and the correlator ────────────────────

def test_the_public_key_is_read_lazily_per_request_not_at_import(keys):
    """The 2026-09-19 defect class. A module-scope read caches for the life of the execution
    environment, so a key rotation would not take effect until every warm sandbox recycled.

    Two halves: the reader is called INSIDE `verify`, once per call; and the module contains no
    boto3 client and no `get_secret_value`, so it could not read at import even by accident.
    """
    calls: list = []
    token = sign(keys, load("get_balance"))
    assert calls == [], "the module read a secret at import"
    verify(keys, token, calls=calls)
    assert calls == [auth.SECRET_ID]
    verify(keys, token, calls=calls)
    assert calls == [auth.SECRET_ID, auth.SECRET_ID], "the key was cached across requests"

    imports = {alias.name.split(".")[0] for node in ast.walk(TREE)
               if isinstance(node, ast.Import) for alias in node.names}
    imports |= {(node.module or "").split(".")[0] for node in ast.walk(TREE)
                if isinstance(node, ast.ImportFrom)}
    assert "boto3" not in imports
    assert "os" not in imports
    assert "get_secret_value" not in SOURCE
    assert "batch_get_secret_value" not in SOURCE


def test_the_public_key_and_pepper_never_appear_in_a_logging_expression():
    """Stronger than "must not be logged": this module LOGS NOTHING AT ALL.

    CodeQL's `py/clear-text-logging-sensitive-data` failed this repository's build twice on a line
    that could not leak anything - a ternary on a key's truthiness - and it was right to: the
    analysis cannot prove the value is discarded, and neither can a reviewer at a glance. It also
    tracks taint across function boundaries, so reducing a secret to a bool in a helper does not
    launder it. The safest shape is no logger here, and the handler logs only the route.

    Over the AST, not the text, because the paragraph above necessarily contains the word
    `logging` - the same reason `tests/test_payment_vocabulary_at_decision_points.py` walks the AST
    rather than grepping its subject.
    """
    imports = {alias.name.split(".")[0] for node in ast.walk(TREE)
               if isinstance(node, ast.Import) for alias in node.names}
    imports |= {(node.module or "").split(".")[0] for node in ast.walk(TREE)
                if isinstance(node, ast.ImportFrom)}
    assert "logging" not in imports

    names = {node.id for node in ast.walk(TREE) if isinstance(node, ast.Name)}
    assert "logger" not in names
    assert "print" not in names

    logging_calls = [node for node in ast.walk(TREE)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                     and node.func.attr in ("info", "warning", "error", "debug", "exception")]
    assert not logging_calls

    # And no exception message INTERPOLATES a key, a token segment or a claim value. Checked on
    # the VALUES an argument reaches, not on its prose: "the token header is not an object" names
    # the token and carries none of it, which is exactly the distinction that matters. The one
    # interpolation permitted is `type(exc).__name__`, which is a class name and nothing else.
    tainted = {"public_key", "public_key_pem", "secret", "claims", "token", "raw_body",
               "header_segment", "payload_segment", "signature_segment", "signing_input",
               "pepper", "audience"}
    for node in ast.walk(TREE):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        for argument in node.exc.args:
            if isinstance(argument, ast.Constant):
                continue          # a plain literal message carries nothing
            reached = {child.id for child in ast.walk(argument)
                       if isinstance(child, ast.Name)}
            leaking = reached & tainted
            assert not leaking, (
                f"line {node.lineno} interpolates {sorted(leaking)} into an exception message: "
                f"{ast.unparse(argument)}")


def test_the_envelope_metadata_request_id_is_the_log_correlator():
    """Wix offers `requestId` for exactly this - "You may print this ID to your logs to help with
    future debugging and easier correlation with Wix's logs" - which is why no masked-value guessing
    is needed on this path and the gift-card code never has to appear in a log line."""
    handler = ROOT / "amplify/functions/ecommerce/wix-giftcard-spi/handler.py"
    tree = ast.parse(handler.read_text(encoding="utf-8"), filename=str(handler))
    logged = [ast.unparse(call) for call in ast.walk(tree)
              if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
              and isinstance(call.func.value, ast.Name) and call.func.value.id == "logger"]
    assert logged
    assert any("requestId" in rendered for rendered in logged)

    # Keyed, not substring-matched: `refusalCode` and `applicationCode` are legitimate keys that
    # contain the word, and a substring test would either fail on them or be loosened until it
    # stopped catching the one key that matters.
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "logger"):
            continue
        for node in ast.walk(call):
            if not isinstance(node, ast.Dict):
                continue
            keys = [key.value for key in node.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)]
            assert "code" not in keys, (
                f"line {call.lineno} logs a gift-card code: {ast.unparse(call)}")
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "codeLast4":
                    assert "masked(" in ast.unparse(value), (
                        f"line {call.lineno} logs codeLast4 unmasked")


# ── 16 / 17 are asserted in the handler's own contract file ────────────────────

def test_verification_is_a_pure_function_of_the_body_and_touches_no_table():
    """Tests 16 and 17 pin the HANDLER's ordering - the store as a spy, zero calls on a bad token -
    and live in `tests/test_gift_card_spi_contract.py` where the handler is exercised. The property
    THIS module contributes is the stronger one: it cannot touch a table, because it is given no
    table to touch."""
    verify_fn = next(node for node in ast.walk(TREE)
                     if isinstance(node, ast.FunctionDef) and node.name == "verify")
    parameters = {argument.arg for argument in verify_fn.args.args} | {
        argument.arg for argument in verify_fn.args.kwonlyargs}
    assert parameters == {"raw_body", "headers", "now", "reader", "is_base64_encoded",
                          "secret_id"}
    # Over the AST: the docstring naming the IAM/table test file necessarily contains "table".
    attributes = {node.func.attr for node in ast.walk(TREE)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    for forbidden in ("Table", "put_item", "get_item", "update_item", "delete_item", "query",
                      "scan", "resource", "client"):
        assert forbidden not in attributes
    names = {node.id for node in ast.walk(TREE) if isinstance(node, ast.Name)}
    assert not {"boto3", "dynamodb", "table"} & names


# ── amounts: the entry point is the float risk ─────────────────────────────────

def test_claims_are_parsed_with_decimal_so_no_float_is_constructed(keys, monkeypatch):
    """`parse_float=Decimal` is MANDATORY and is asserted by making `float` itself raise.

    The SPI sends amounts as JSON NUMBERS, and `json.loads` produces a float for `12.34` by
    default - at the very entry point, before a single line of our own logic runs.
    """
    import builtins

    token = sign(keys, load("redeem"))
    reader = reader_for(keys)

    def refuse(*_args, **_kwargs):
        raise AssertionError("a float was constructed while parsing SPI claims")

    monkeypatch.setattr(builtins, "float", refuse)
    verified = auth.verify(token, headers={}, now=NOW, reader=reader)
    amount = verified.request["amount"]
    assert isinstance(amount, Decimal)
    assert amount == Decimal("400.00")
    assert "parse_float=Decimal" in SOURCE


def test_the_three_fixtures_are_the_three_documented_request_shapes():
    """`GetBalanceRequest` and `RedeemRequest` carry a `code`; `VoidRequest` carries NO code and
    identifies the transaction by id alone, which is the measurement the `GCTXNID#` row exists
    for."""
    balance = load("get_balance")["data"]["request"]
    redeem = load("redeem")["data"]["request"]
    void = load("void")["data"]["request"]

    assert "code" in balance and "code" in redeem
    assert "code" not in void
    assert "transactionId" in void and "transactionId" not in redeem
    assert "currencyCode" in redeem and "currencyCode" not in balance
    assert "orderId" in redeem
    # `amount` is a JSON number in the file, not a quoted string.
    raw = (FIXTURES / "wix_spi_redeem_jwt_payload.json").read_text(encoding="utf-8")
    assert '"amount": 400.00' in raw
    for payload in (load("get_balance"), load("redeem"), load("void")):
        assert payload["iss"] == "wix.com"
        assert payload["aud"] == APP_ID
        assert set(payload["data"]) == {"request", "metadata"}
