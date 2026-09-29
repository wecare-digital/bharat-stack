"""`meta_error_summary` must never let a provider's prose reach a log.

WHY IT EXISTS. `_send_via_aws` in `amplify/functions/messaging/whatsapp-calling/handler.py`
returns the **raw Meta response** on its error branch, and three log sites dumped it whole.
Two of them did so on the same line as `mask_phone(to_number or '')`, which is the exact
shape `docs/security-codeql-triage.md` records finding once before: the number masked on
the left of the line and reprinted unmasked on the right.

Meta writes the recipient into the prose of several messaging errors -- 131030 is the
well-known one -- and `error_data.details` is free text in general. So the test that matters
is not "does it return the code", it is **"is the number absent from the output"**, and the
fixtures below are real Meta error shapes carrying a number in the prose.

`json.dumps(...)[:500]` is not a fix and there is a case for that too: truncation removes a
suffix, not a phone number sitting at character 40.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "amplify" / "functions" / "shared" / "lambda_utils" / "masking.py"

_spec = importlib.util.spec_from_file_location("masking_under_test", MODULE)
masking = importlib.util.module_from_spec(_spec)
sys.modules["masking_under_test"] = masking
_spec.loader.exec_module(masking)

summary = masking.meta_error_summary

#: A real 131030 shape. The recipient appears in `message` and again in `error_data`.
NUMBER = "918100640044"
META_131030 = {
    "error": {
        "message": (
            f"(#131030) Recipient phone number not in allowed list: Add recipient phone "
            f"number +{NUMBER} to Recipient List and try again."
        ),
        "type": "OAuthException",
        "code": 131030,
        "error_data": {"messaging_product": "whatsapp",
                       "details": f"Recipient +{NUMBER} is not in allowed list"},
        "error_subcode": 2655007,
        "fbtrace_id": "AbCdEfGhIjK",
    }
}


class TestNoProviderProseReachesTheOutput:
    def test_the_recipient_number_is_absent(self):
        out = summary(META_131030)
        assert NUMBER not in out
        # Also absent in the spaced and dashed renderings a provider might use.
        for variant in (NUMBER, f"+{NUMBER}", NUMBER[-10:], NUMBER[-4:]):
            assert variant not in out, f"{variant!r} survived in {out!r}"

    def test_no_message_or_details_text_survives(self):
        out = summary(META_131030)
        for fragment in ("Recipient", "allowed list", "try again", "messaging_product"):
            assert fragment not in out, f"{fragment!r} survived in {out!r}"

    def test_the_identifiers_a_human_debugs_from_are_kept(self):
        out = summary(META_131030)
        assert "code=131030" in out
        assert "type=OAuthException" in out
        assert "error_subcode=2655007" in out
        assert "fbtrace_id=AbCdEfGhIjK" in out

    def test_it_records_that_a_message_existed_without_quoting_it(self):
        # Losing the fact that Meta said something would make the log worse, not safer.
        assert "message_present=True" in summary(META_131030)
        assert "message_present" not in summary({"error": {"code": 5}})


class TestTheOtherShapesThisFunctionReceives:
    def test_our_own_detail_string_is_reduced_to_its_length(self):
        # `_send_via_aws` also returns `{'error': True, 'detail': str(exc)}`, and an
        # exception's text is provider text by the same argument.
        out = summary({"error": True, "detail": f"HTTPError: recipient +{NUMBER} rejected"})
        assert NUMBER not in out
        assert "detail_len=" in out

    def test_error_true_with_no_detail(self):
        assert summary({"error": True}) == "error=True (no detail)"

    def test_a_success_result_is_reported_as_such_not_as_empty(self):
        # A blank string at an error log site reads as a missing field.
        assert summary({"success": True, "messageId": "wamid.X"}) == "no error field"

    @pytest.mark.parametrize("value", [None, "boom", 42, [], object()])
    def test_a_non_dict_never_raises(self, value):
        out = summary(value)
        assert isinstance(out, str) and out


class TestItIsWiredIntoTheHandler:
    def test_no_log_site_in_whatsapp_calling_dumps_a_raw_send_result(self):
        """The three remediated sites must not drift back to dumping the whole response."""
        source = (ROOT / "amplify" / "functions" / "messaging" / "whatsapp-calling"
                  / "handler.py").read_text(encoding="utf-8")
        offenders = [
            (n, line.strip())
            for n, line in enumerate(source.splitlines(), 1)
            if "logger." in line
            and ("json.dumps(result)" in line or ": {result}" in line)
            and "meta_error_summary" not in line
        ]
        # Five same-class sites elsewhere in this file are recorded in
        # docs/security-codeql-triage.md and are NOT yet remediated, so this asserts only
        # on the ones that were. Tightening it to zero is the follow-up.
        remediated_lines = {1245, 2097, 2125, 2127}
        regressed = [o for o in offenders if o[0] in remediated_lines]
        assert not regressed, f"a remediated site went back to dumping the raw result: {regressed}"
