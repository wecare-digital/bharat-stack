"""Tests for the Cognito CustomMessage trigger.

The failure mode that matters most is not "the email looks wrong" but "Cognito
rejects the response and the message is never sent", which locks someone out of
their own account. So the placeholder invariants are asserted hardest.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

HANDLER_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "amplify/functions/auth/cognito-custom-message/handler.py"
)

spec = importlib.util.spec_from_file_location("cognito_custom_message", HANDLER_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def event(trigger: str, code: str = "{####}", username: str | None = None) -> dict:
    request: dict = {"codeParameter": code, "userAttributes": {}}
    if username is not None:
        request["usernameParameter"] = username
    return {"triggerSource": trigger, "request": request, "response": {}}


ALL_SOURCES = [
    "CustomMessage_Authentication",
    "CustomMessage_SignUp",
    "CustomMessage_ResendCode",
    "CustomMessage_ForgotPassword",
    "CustomMessage_UpdateUserAttribute",
    "CustomMessage_VerifyUserAttribute",
    "CustomMessage_AdminCreateUser",
]


class TestPlaceholderInvariants:
    """Cognito rejects a response whose body lacks the placeholder."""

    @pytest.mark.parametrize("trigger", ALL_SOURCES)
    def test_body_always_contains_the_code_placeholder(self, trigger):
        out = mod.handler(event(trigger, username="newperson"), None)
        assert out["response"]["emailMessage"].count("{####}") >= 1

    def test_uses_the_placeholder_cognito_supplied_not_a_hardcoded_one(self):
        # The docs say to reference request.codeParameter rather than assume
        # {####}. If this function hardcoded it, a different placeholder would
        # silently produce an email with no code in it at all.
        out = mod.handler(event("CustomMessage_Authentication", code="%%CODE%%"), None)
        body = out["response"]["emailMessage"]
        assert "%%CODE%%" in body
        assert "{####}" not in body

    def test_admin_create_includes_the_username_placeholder(self):
        # An admin-created user must receive their username as well as the code,
        # or they cannot sign in at all.
        out = mod.handler(
            event("CustomMessage_AdminCreateUser", username="{username}"), None)
        body = out["response"]["emailMessage"]
        assert "{username}" in body
        assert "{####}" in body

    def test_refuses_rather_than_returns_a_body_cognito_would_reject(self):
        # Belt and braces: if a future edit drops the placeholder from the
        # template, fail loudly here instead of at delivery time.
        original = mod.build_email
        mod.build_email = lambda *a, **k: "<html>no placeholder</html>"
        try:
            with pytest.raises(ValueError, match="code placeholder"):
                mod.handler(event("CustomMessage_Authentication"), None)
        finally:
            mod.build_email = original


class TestEveryTriggerSourceIsHandled:
    @pytest.mark.parametrize("trigger", ALL_SOURCES)
    def test_known_sources_get_their_own_subject_and_heading(self, trigger):
        out = mod.handler(event(trigger, username="x"), None)
        assert out["response"]["emailSubject"]
        assert "WECARE.DIGITAL" in out["response"]["emailSubject"] \
            or "Confirm" in out["response"]["emailSubject"] \
            or "Reset" in out["response"]["emailSubject"] \
            or "Verify" in out["response"]["emailSubject"]

    def test_subjects_are_distinguishable_across_sources(self):
        # The owner reported two emails arriving and not being able to tell them
        # apart. Distinct subjects are the cheapest fix for that.
        subjects = {
            mod.handler(event(t, username="x"), None)["response"]["emailSubject"]
            for t in ALL_SOURCES
        }
        assert len(subjects) == len(ALL_SOURCES)

    def test_an_unknown_source_still_produces_a_usable_email(self):
        out = mod.handler(event("CustomMessage_SomethingNew"), None)
        assert "{####}" in out["response"]["emailMessage"]
        assert out["response"]["emailSubject"]

    def test_missing_code_parameter_falls_back_to_the_documented_default(self):
        ev = {"triggerSource": "CustomMessage_Authentication",
              "request": {}, "response": {}}
        out = mod.handler(ev, None)
        assert "{####}" in out["response"]["emailMessage"]


class TestEmailClientCompatibility:
    """These are the four deliberate deviations from the browser contract."""

    def setup_method(self):
        self.body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]

    def test_no_rgba_anywhere(self):
        # Outlook's Word engine drops rgba() declarations, falling back to
        # unstyled black. The composited hex equivalents render identically.
        assert "rgba(" not in self.body

    def test_no_opacity_which_outlook_ignores(self):
        # An ignored opacity would render a muted label at full white, competing
        # with the code itself. #b7b7b7 is that grey, composited.
        assert "opacity:" not in self.body

    def test_no_clamp_and_no_css_variables(self):
        assert "clamp(" not in self.body
        assert "var(--" not in self.body

    def test_no_flex_or_grid_layout(self):
        assert "display:flex" not in self.body
        assert "display:grid" not in self.body

    def test_layout_is_table_based_with_inline_styles(self):
        assert self.body.count("<table") >= 3
        assert 'role="presentation"' in self.body
        # Gmail strips <style> in forwarded mail, so there must not be one.
        assert "<style" not in self.body


class TestContractValuesSurvive:
    def setup_method(self):
        self.body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]

    def test_inter_leads_the_font_stack(self):
        assert "'Inter'" in self.body

    def test_hairline_is_the_contract_grey(self):
        assert "#e5e7eb" in self.body

    def test_code_panel_is_black_with_the_contract_radius(self):
        assert "background:#000000" in self.body
        assert "border-radius:14px" in self.body

    def test_our_own_mark_is_lime_fill_with_dark_green_type(self):
        assert f"background:{mod.LIME};color:{mod.DARK_GREEN}" in self.body

    def test_card_uses_the_static_radius_and_hairline(self):
        assert "border-radius:20px" in self.body

    def test_composited_colours_match_the_contract_arithmetic(self):
        # rgba(0,0,0,.898) over white == #1a1a1a, which is also the contract's
        # own brand near-black, so this substitution is exact rather than close.
        assert mod.BODY == "#1a1a1a"
        assert mod.HEADING == "#0d0d0d"
        assert mod.MUTED == "#757575"

    def test_carries_no_retired_colour(self):
        for dead in ("#4b5563", "#111827", "#1e293b", "#0f172a", "#94a3b8",
                     "#2f6b52", "#075e54", "#f2fbf6", "#fbfff0", "#1e1e1e"):
            assert dead not in self.body

    def test_no_uppercase_transform_on_labels(self):
        assert "text-transform:uppercase" not in self.body


class TestClarity:
    """The reported problem was "not clear", so these pin readability."""

    def test_single_code_panel_carries_no_label_that_repeats_the_heading(self):
        out = mod.handler(event("CustomMessage_Authentication"), None)
        body = out["response"]["emailMessage"]
        # "Your sign-in code" should appear once - as the heading - not twice.
        assert body.count("Your sign-in code") == 1

    def test_admin_create_labels_its_two_panels_so_they_can_be_told_apart(self):
        body = mod.handler(
            event("CustomMessage_AdminCreateUser", username="{username}"),
            None)["response"]["emailMessage"]
        assert "Username" in body
        assert "Temporary password" in body
        assert body.count("background:#000000") == 2

    def test_only_one_code_panel_for_a_normal_message(self):
        body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]
        assert body.count("background:#000000") == 1

    def test_says_who_sent_it_and_from_where(self):
        body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]
        assert "one@wecare.digital" in body

    def test_warns_that_nobody_will_ask_for_the_code(self):
        body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]
        assert "ask you for this code" in body

    def test_says_a_new_code_replaces_the_old_one(self):
        # This is what makes two emails in an inbox comprehensible rather than
        # alarming: the second one says the first is dead.
        body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]
        assert "replaces it" in body


class TestSafety:
    def test_the_function_never_sees_a_real_code_so_nothing_needs_redacting(self):
        # codeParameter is a placeholder; Cognito substitutes the value after
        # this returns. Asserted so nobody later "improves" the function by
        # resolving the code itself, which would put a live OTP in a log.
        out = mod.handler(event("CustomMessage_Authentication", code="{####}"), None)
        assert "{####}" in out["response"]["emailMessage"]

    def test_body_is_well_under_the_cognito_template_limit(self):
        body = mod.handler(
            event("CustomMessage_AdminCreateUser", username="{username}"),
            None)["response"]["emailMessage"]
        assert len(body) < 20000

    def test_returns_the_whole_event_not_just_the_response(self):
        # Cognito expects the full event back; returning only the response is a
        # silent no-op that leaves the default message in place.
        ev = event("CustomMessage_Authentication")
        out = mod.handler(ev, None)
        assert out is ev
        assert "triggerSource" in out

    def test_html_is_balanced_enough_to_render(self):
        body = mod.handler(
            event("CustomMessage_Authentication"), None)["response"]["emailMessage"]
        assert body.count("<table") == body.count("</table>")
        assert body.count("<tr") == body.count("</tr>")
        assert len(re.findall(r"<td", body)) == len(re.findall(r"</td>", body))
