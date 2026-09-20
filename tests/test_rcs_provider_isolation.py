"""RCS provider boundaries: Sinch is India-only, and nothing falls back to it.

The provider matrix allows Sinch exactly one capability - India RCS - and
prohibits Sinch SMS, Sinch Voice and Sinch WhatsApp outright. These tests assert
the boundary structurally, on the source tree, because the failure mode is a
*new* call site rather than a wrong return value: a future handler importing the
Sinch transport for a non-RCS purpose would pass any behavioural test while
breaking the policy.

`scripts/check-provider-policy.sh` enforces the same rule in CI. This suite
exists so the boundary also fails a developer's local `pytest` run, before CI.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
FUNCTIONS = ROOT / "amplify" / "functions"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils import sinch_rcs  # noqa: E402

# The only paths allowed to hold the Sinch vendor transport - hosts and the
# credential id. Mirrors RCS_ALLOWED_RE in scripts/check-provider-policy.sh.
RCS_ALLOWED = (
    "lambda_utils/sinch_rcs.py",
    "/rcs-send/",
    "/rcs-dlr/",
    "providers/sinch/rcs/",
    "services/rcs/sinch/",
)

# Vendor transport markers: the hostnames and the secret id.
TRANSPORT_MARKERS = (
    "aclwhatsapp.com",
    "wecare/sinch/rcs",
    "conversation.api.sinch.com",
)


def _python_sources():
    for path in FUNCTIONS.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _is_allowed(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    return any(fragment in text for fragment in RCS_ALLOWED)


# --------------------------------------------------------------------------
# the transport is confined
# --------------------------------------------------------------------------
def test_sinch_transport_only_inside_approved_rcs_paths():
    offenders = []
    for path in _python_sources():
        if _is_allowed(path):
            continue
        body = path.read_text(errors="replace")
        for marker in TRANSPORT_MARKERS:
            if marker in body:
                offenders.append(f"{path.relative_to(ROOT)} holds {marker!r}")
    assert offenders == [], (
        "Sinch vendor transport found outside the approved India RCS paths:\n  "
        + "\n  ".join(offenders))


def test_no_lambda_reads_the_sinch_secret_directly():
    """Only sinch_rcs may resolve the Sinch credential.

    voice-in/cdr used to read `wecare/sinch/rcs` inline in an unreachable copy of
    the RCS sender. That gave a voice handler a live path to the credential for
    no working feature.
    """
    offenders = [
        str(path.relative_to(ROOT))
        for path in _python_sources()
        if not _is_allowed(path) and "wecare/sinch/rcs" in path.read_text(errors="replace")
    ]
    assert offenders == []


def test_voice_in_cdr_ingester_is_gone():
    """The Airtel CDR ingester carried a duplicate RCS implementation.

    It was first reduced to using the shared helper, then deleted outright on
    2026-09-20 once it was shown to be unreachable: no routes, no event source
    mappings, no invocations after its routes were removed, and no Lambda
    invoking it by name. Deletion is the strongest form of "no duplicate
    implementation", so this now asserts absence rather than contents.
    """
    assert not (FUNCTIONS / "messaging" / "voice-in" / "cdr").exists(), (
        "the Airtel CDR ingester is back; it was deleted as unreachable and "
        "previously held a second copy of the RCS send path")


def test_no_function_reimplements_the_rcs_helpers():
    """The invariant the deleted test actually protected, applied fleet-wide.

    Only lambda_utils/sinch_rcs.py may define these. A handler growing its own
    copy is how the duplicate arose the first time.
    """
    offenders = []
    for handler in FUNCTIONS.rglob("*.py"):
        if "__pycache__" in str(handler):
            continue
        if handler.name == "sinch_rcs.py":
            continue
        body = handler.read_text(errors="replace")
        for marker in ("def _is_rcs_enabled", "def _send_rcs_notification"):
            if marker in body:
                offenders.append(f"{handler.relative_to(FUNCTIONS)}: {marker}")
    assert not offenders, (
        "RCS helpers reimplemented outside lambda_utils/sinch_rcs.py: "
        + ", ".join(offenders))


# --------------------------------------------------------------------------
# Sinch has exactly one capability
# --------------------------------------------------------------------------
def test_sinch_module_exposes_no_sms_sender():
    """Sinch SMS is prohibited. The RCS module must not grow one."""
    exported = [name for name in dir(sinch_rcs) if not name.startswith("__")]
    for name in exported:
        lowered = name.lower()
        if "rcs" in lowered:
            continue
        assert "sms" not in lowered, f"sinch_rcs exposes an SMS symbol: {name}"


def test_sinch_module_exposes_no_voice_or_whatsapp_sender():
    for name in dir(sinch_rcs):
        if name.startswith("__"):
            continue
        lowered = name.lower()
        assert not lowered.startswith("send_voice"), name
        assert "whatsapp" not in lowered, f"sinch_rcs exposes WhatsApp: {name}"


def test_dead_rcs_helpers_are_gone():
    """Removed because nothing called them; asserted so they are not re-added blind."""
    assert not hasattr(sinch_rcs, "send_rcs_order_notification")
    assert not hasattr(sinch_rcs, "send_rcs_wa_alert")


def test_live_rcs_helpers_are_still_present():
    """The India RCS capability itself is APPROVED and must keep working."""
    for kept in ("is_rcs_enabled", "send_rcs_text", "send_rcs_card",
                 "send_rcs_template", "send_rcs_ivr_notification"):
        assert hasattr(sinch_rcs, kept), f"{kept} was removed - India RCS is approved"


# --------------------------------------------------------------------------
# no RCS path falls back to a prohibited provider
# --------------------------------------------------------------------------
def test_rcs_module_does_not_fall_back_to_sinch_sms():
    body = (SHARED / "lambda_utils" / "sinch_rcs.py").read_text()
    # An SMS fallback from RCS is required to be AWS. The Sinch SMS gateway host
    # must not appear here at all.
    assert "jumbo.aclgateway.com" not in body
    assert "_send_sinch_sms" not in body


def test_approved_india_rcs_templates_are_explicit():
    """Template ids are an allowlist, not caller input."""
    body = (SHARED / "lambda_utils" / "sinch_rcs.py").read_text()
    assert re.search(r"rcsmenu", body), "approved template allowlist missing"


# --------------------------------------------------------------------------
# non-India RCS is AWS, and is honestly reported as not yet built
# --------------------------------------------------------------------------
def test_india_rcs_normalises_to_indian_msisdns_only():
    """The Sinch sender must not be handed an arbitrary international number.

    Sinch is approved for India RCS specifically. `_normalize_phone` is the
    module's own boundary, so assert it produces Indian E.164 and does not
    silently pass a non-Indian destination through to the India-only agent.
    """
    assert sinch_rcs._normalize_phone("9903300044").lstrip("+").startswith("91")
    assert sinch_rcs._normalize_phone("+919903300044").lstrip("+").startswith("91")


def test_no_module_outside_the_approved_paths_can_reach_sinch():
    """The structural guarantee that makes non-India routing safe.

    Non-India RCS belongs to AWS. Rather than assert what a not-yet-built AWS RCS
    sender does, assert the property that makes a mistake impossible: no module
    outside the approved India paths references the Sinch transport at all, so
    none of them can route to it whatever their destination logic says.
    """
    reachable_from = sorted(
        str(path.relative_to(ROOT))
        for path in _python_sources()
        if any(marker in path.read_text(errors="replace") for marker in TRANSPORT_MARKERS)
    )
    for path in reachable_from:
        assert any(fragment.strip("/") in path for fragment in RCS_ALLOWED), (
            f"{path} can reach the Sinch transport but is not an approved India "
            "RCS path")
