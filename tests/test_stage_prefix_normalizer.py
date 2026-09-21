"""One stage-prefix rule, one implementation, and the six cases the brief names.

Provenance
----------
The API Gateway custom domain mapping puts the stage in the path, so a request to
`https://api.wecare.digital/whatsapp` arrives as `/prod/whatsapp`. That has caused
two production incidents:

  * `plivo-answer` - signature verification computed over the wrong URL, so every
    genuine Plivo callback failed a fail-closed check.
  * `whatsapp-calling` - `"/prod/whatsapp" != "/whatsapp"`, so the public webhook
    branch was skipped and execution fell through to the admin auth gate. 532
    consecutive 401s to Meta in 12 hours; `wecare-inbound-whatsapp` received zero
    invocations because nothing forwarded to it.

Each incident was fixed by re-deriving the rule locally. By 2026-09-21 there were
three copies, and the hand-rolled one in `core/url-shortener` was the only one
that handled a path of exactly `/{stage}`. The rule now lives in
`lambda_utils/http_path.py` and every site imports it.

The brief names six regression cases for the WhatsApp ingress specifically. Cases
1-3 and 6 are covered behaviourally in `tests/test_whatsapp_calling_stage_prefix.py`;
this file covers the normalizer itself, cases 4 and 5, and the consolidation.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
FUNCTIONS = ROOT / "amplify" / "functions"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.http_path import normalize_path, strip_stage  # noqa: E402


def ev(path, stage="prod", *, use_http_path=False):
    rc = {"stage": stage}
    if use_http_path:
        rc["http"] = {"path": path}
        return {"requestContext": rc}
    return {"rawPath": path, "requestContext": rc}


class TestTheRule:
    def test_stage_prefix_is_stripped(self):
        assert normalize_path(ev("/prod/whatsapp")) == "/whatsapp"

    def test_path_without_a_stage_prefix_is_untouched(self):
        """Brief case 4: /whatsapp without a stage continues to work."""
        assert normalize_path(ev("/whatsapp")) == "/whatsapp"

    def test_a_different_stage_name_is_not_stripped(self):
        """Brief case 5: /production/whatsapp must NOT be stripped when the
        actual stage is 'prod'. A prefix match on the string alone would eat it."""
        assert normalize_path(ev("/production/whatsapp", stage="prod")) == \
            "/production/whatsapp"

    def test_stripping_is_driven_by_the_stage_not_a_literal(self):
        """A hardcoded 'prod' reintroduces the incident on any second stage."""
        assert normalize_path(ev("/staging/whatsapp", stage="staging")) == "/whatsapp"
        assert normalize_path(ev("/dev/plivo/answer", stage="dev")) == "/plivo/answer"

    def test_default_stage_is_left_alone(self):
        """$default does not appear in the path."""
        assert normalize_path(ev("/whatsapp", stage="$default")) == "/whatsapp"

    def test_missing_stage_is_left_alone(self):
        assert normalize_path({"rawPath": "/whatsapp", "requestContext": {}}) == "/whatsapp"
        assert normalize_path({"rawPath": "/whatsapp"}) == "/whatsapp"

    def test_bare_stage_becomes_root(self):
        """The case only url-shortener handled. For a short-link service, '/prod'
        must be the root, not a lookup for a code called 'prod'."""
        assert normalize_path(ev("/prod")) == "/"

    def test_trailing_slash_on_the_bare_stage(self):
        assert normalize_path(ev("/prod/")) == "/"

    def test_empty_path_becomes_root(self):
        assert normalize_path(ev("")) == "/"
        assert normalize_path({}) == "/"

    def test_falls_back_to_the_http_context_path(self):
        assert normalize_path(ev("/prod/whatsapp", use_http_path=True)) == "/whatsapp"

    def test_falls_back_to_the_rest_style_path_key(self):
        assert normalize_path(
            {"path": "/prod/whatsapp", "requestContext": {"stage": "prod"}}
        ) == "/whatsapp"

    def test_a_stage_named_segment_deeper_in_the_path_is_kept(self):
        assert normalize_path(ev("/prod/a/prod/b")) == "/a/prod/b"

    def test_string_form_agrees_with_the_event_form(self):
        assert strip_stage("/prod/whatsapp", "prod") == "/whatsapp"
        assert strip_stage("/prod", "prod") == "/"


class TestOneImplementation:
    """Three copies of this rule is how the bug came back a second time."""

    def test_plivo_signature_re_exports_rather_than_redefining(self):
        src = (SHARED / "lambda_utils" / "plivo_signature.py").read_text()
        assert "from lambda_utils.http_path import normalize_path" in src
        assert "def normalize_path" not in src

    def test_the_re_export_is_the_same_function(self):
        from lambda_utils.plivo_signature import normalize_path as via_plivo
        assert via_plivo is normalize_path

    @pytest.mark.parametrize("rel", [
        "messaging/whatsapp-calling",
        "messaging/plivo-answer",
        "core/url-shortener",
    ])
    def test_each_site_imports_the_shared_helper(self, rel):
        src = (FUNCTIONS / rel / "handler.py").read_text()
        assert "normalize_path" in src, rel

    @pytest.mark.parametrize("rel", [
        "messaging/whatsapp-calling",
        "messaging/plivo-answer",
        "core/url-shortener",
    ])
    def test_no_site_re_derives_the_stripping_logic(self, rel):
        """The hand-rolled form is `path.startswith(f"/{stage}")`."""
        src = (FUNCTIONS / rel / "handler.py").read_text()
        assert 'startswith(f"/{stage}' not in src, rel
        assert "startswith(f'/{stage}" not in src, rel


class TestUrlShortenerKeepsItsBehaviour:
    """The consolidation must not regress the case url-shortener alone handled."""

    def test_bare_stage_still_resolves_to_root_for_short_links(self):
        assert normalize_path(ev("/prod")) == "/"

    def test_a_short_code_is_still_a_short_code(self):
        assert normalize_path(ev("/prod/abc123")) == "/abc123"

    def test_the_r_form_survives(self):
        assert normalize_path(ev("/prod/r/abc123")) == "/r/abc123"
