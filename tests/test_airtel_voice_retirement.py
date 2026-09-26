"""Airtel voice is retired: the diallers are gone, the history is not.

The SMS retirement deleted whole functions. Voice could not be done that way,
because two of the three functions also carried capabilities that are not
provider-specific and that the operations UI depends on:

  * `voice-in/obd` owns Polly text-to-speech and the S3 IVR prompt library;
  * both `voice-in/c2c` and `voice-in/obd` ingest CDR callbacks and read
    historical records that are retained as audit evidence.

So the prohibited surface was excised and the rest kept. These tests pin that
split, because a partial removal is much easier to get wrong than a deletion:
the danger is a dialler that still works via a forgotten call site, or a
capability accidentally taken out with it.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
MESSAGING = ROOT / "amplify" / "functions" / "messaging"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

C2C = MESSAGING / "voice-in" / "c2c" / "handler.py"
OBD = MESSAGING / "voice-in" / "obd" / "handler.py"


def _tree(path: Path):
    return ast.parse(path.read_text())


def _functions(path: Path):
    return {n.name for n in ast.walk(_tree(path)) if isinstance(n, ast.FunctionDef)}


# --------------------------------------------------------------------------
# the pure dialler is gone entirely
# --------------------------------------------------------------------------
def test_outbound_voice_function_is_deleted():
    """It was 100% retired-provider dialling, with no compliant surface to keep."""
    assert not (MESSAGING / "outbound-voice").exists()


def test_outbound_voice_is_not_in_the_deploy_map():
    body = (ROOT / "scripts" / "deploy_all_lambdas.py").read_text()
    assert '"wecare-outbound-voice"' not in body


def test_outbound_voice_has_no_iam_grant():
    body = (ROOT / "amplify" / "iam-policies.ts").read_text()
    assert "'wecare-outbound-voice'" not in body
    # and neither does its alias
    assert "'wecare-voice-calls':" not in body


def test_outbound_voice_has_no_log_retention_entry():
    body = (ROOT / "amplify" / "backend-resources.ts").read_text()
    assert "'wecare-outbound-voice'" not in body


# --------------------------------------------------------------------------
# the dialling code is gone from the surviving functions
# --------------------------------------------------------------------------
def test_c2c_dialler_functions_are_gone():
    functions = _functions(C2C)
    for gone in ("_make_c2c_call", "_generate_hmac_headers", "_get_secrets"):
        assert gone not in functions, f"{gone} still defined in voice-in/c2c"


def test_obd_dialler_functions_are_gone():
    functions = _functions(OBD)
    for gone in ("_create_campaign", "_upload_csv", "_upload_csv_internal",
                 "_get_campaign_status", "_upload_audio", "_get_secrets",
                 "_extract_audio_url"):
        assert gone not in functions, f"{gone} still defined in voice-in/obd"


@pytest.mark.parametrize("path", [C2C, OBD])
def test_no_retired_provider_credential_is_read(path):
    """Neither function may resolve a RETIRED provider credential any more.

    Narrowed deliberately: both still read `wecare/meta-system-user-token` for the
    WhatsApp leg of the CDR notification fan-out, which is an approved provider and
    must keep working. Asserting "no get_secret_value at all" would have demanded
    the removal of a compliant capability.
    """
    body = path.read_text()
    for secret_id in ("wecare/airtel", "airtel/c2c", "airtel/obd", "airtel/sms",
                      "airtel-iq", "sinch/sms"):
        assert secret_id not in body, f"{path.name} still names {secret_id}"


@pytest.mark.parametrize("path", [C2C, OBD])
def test_no_undefined_calls_after_excision(path):
    """A partial removal can leave a call to a function that no longer exists.

    That would be an AttributeError at request time rather than at import, so it
    is worth asserting structurally.
    """
    tree = _tree(path)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    dangling = sorted(c for c in called if c.startswith("_") and c not in defined)
    assert dangling == [], f"{path.name} calls undefined {dangling}"


@pytest.mark.parametrize("path", [C2C, OBD])
def test_no_vendor_gateway_path_remains(path):
    """No retired-provider API path may survive, in code or in a docstring.

    Asserts vendor GATEWAY PATH fragments, not the words. "click-to-call" is
    ordinary English and legitimately describes what the historical records are;
    "/gateway/airtel-xchange/v2/click-to-call" is a provider endpoint. Only the
    second is a violation, and conflating them would force the documentation to be
    vague about what the retained data is.
    """
    body = path.read_text()
    for marker in ("airtel-xchange", "uploadPrompts", "campaign-manager",
                   "createCampaign", "iqvoice", "iqtelephony", "openapi.airtel"):
        assert marker not in body, f"{path.name} still references {marker}"


# --------------------------------------------------------------------------
# retired endpoints answer 410, explicitly
# --------------------------------------------------------------------------
def test_c2c_initiation_answers_410_not_404():
    """404 would read as "wrong URL". 410 plus a reason says "this moved"."""
    body = C2C.read_text()
    assert "_response(410" in body
    assert "ENDPOINT_REMOVED" in body


def test_obd_has_a_single_retired_endpoint_handler():
    functions = _functions(OBD)
    assert "_retired_campaign_endpoint" in functions
    body = OBD.read_text()
    assert "ENDPOINT_REMOVED" in body


def test_obd_routes_all_four_retired_paths_to_it():
    body = OBD.read_text()
    for path_fragment in ("/upload-audio", "/upload-csv", "/create", "/status"):
        assert path_fragment in body
    # and the default POST no longer reaches a campaign creator
    assert "_create_campaign(body, request_id)" not in body


# --------------------------------------------------------------------------
# what must survive
# --------------------------------------------------------------------------
def test_obd_keeps_text_to_speech_and_the_audio_library():
    """Neither is provider-specific, and the voice operations UI needs both."""
    functions = _functions(OBD)
    for kept in ("_text_to_audio", "_list_audio_library",
                 "_upload_to_audio_library", "_delete_audio_library_file"):
        assert kept in functions, f"{kept} was removed but is not provider-specific"


def test_obd_audio_url_now_points_at_storage_we_control():
    """It used to report a vendor URL even when that upload had silently failed."""
    body = OBD.read_text()
    assert "audio_url = f'https://{S3_BUCKET}/{s3_key}'" in body
    assert "airtelAudioUrl" not in body


@pytest.mark.parametrize("path,keeps", [
    (C2C, ("_list_calls", "_delete_call", "_clear_logs")),
    (OBD, ("_list_campaigns", "_delete_campaign", "_clear_logs")),
])
def test_historical_reads_survive(path, keeps):
    functions = _functions(path)
    for kept in keeps:
        assert kept in functions, f"{kept} removed from {path.name} - history must stay readable"


@pytest.mark.parametrize("path", [C2C, OBD])
def test_the_airtel_cdr_write_path_is_gone(path):
    """Renamed from `..._and_cdr_ingestion_survive`, which protected the wrong thing.

    That test required `_handle_cdr_callback` to survive, justified as "history must
    stay readable". But `_handle_cdr_callback` is a **write** path, and readability of
    history does not depend on it - `_list_calls`, `_list_campaigns` and
    `wecare-voice-cdr-read` all still read `VoiceCDRTable`, which the test above
    pins.

    What it actually preserved was an **Airtel** ingestion branch: a POST shaped like
    an Airtel CDR (`Session_ID`, `Overall_Call_Status`, `participants[]`) was accepted
    and written to `VoiceCDRTable`. Airtel is a retired provider, so nothing sends
    those, and `bw-crm.md` requires zero Airtel executable surface.

    Checked before removing it, 2026-09-25:

    * **Zero** `cdr_callback_received` events in either log group across the full
      30-day retention window, against a control pattern (`REPORT`) that matched in
      the same query - so the absence is a measurement, not an empty result.
    * CDR **ingestion is not lost**: `plivo-answer` writes final call state into
      `VoiceCDRTable` for the live PSTN provider. There is no `/voice-cdr-webhook`
      route any more; only `GET`/`DELETE /voice-cdr-read`.
    * Both functions are live (40 and 41 invocations in that window, 16 routes), so
      this removed a branch, not a dead function.

    This now guards the opposite direction: the branch must not come back.
    """
    body = path.read_text()
    functions = _functions(path)
    for gone in ("_is_cdr_callback", "_handle_cdr_callback", "_normalize_cdr_payload"):
        assert gone not in functions, (
            f"{gone} is back in {path.name}. Airtel is retired; an Airtel-shaped POST "
            "must not be accepted and written to VoiceCDRTable."
        )
    # The table itself stays readable - that is the point of the split.
    assert "VOICE_CDR_TABLE" in body, (
        f"{path.name} no longer references VOICE_CDR_TABLE; historical CDR reads "
        "were supposed to survive"
    )


def test_physical_table_names_are_unchanged():
    """Renaming the table would orphan real historical records.

    The code identifier is provider-neutral now; the table it points at is not
    renamed, because the data in it is evidence.
    """
    assert "LEGACY_C2C_TABLE" in C2C.read_text()
    assert "stack-wecare-digital-AirtelC2CTable" in C2C.read_text()
    assert "stack-wecare-digital-OBDCampaigns" in OBD.read_text()


def test_c2c_and_obd_keep_their_iam_but_lose_the_secrets_grant():
    body = (ROOT / "amplify" / "iam-policies.ts").read_text()
    assert "'wecare-voice-in-c2c'" in body
    assert "'wecare-voice-in-obd'" in body
    # they no longer read a secret, so the grant is narrowed
    for line in body.splitlines():
        if "'wecare-voice-in-c2c'" in line or "'wecare-voice-in-obd'" in line:
            assert "'secrets'" not in line, f"secrets grant retained: {line.strip()}"


def test_voice_cdr_table_is_still_shared_with_plivo():
    """plivo-answer writes into VoiceCDRTable, so it must not be treated as legacy."""
    plivo = (MESSAGING / "plivo-answer" / "handler.py").read_text()
    assert "VoiceCDRTable" in plivo
    assert "'plivo#" in plivo or 'f"plivo#' in plivo or "plivo#{call_uuid}" in plivo
