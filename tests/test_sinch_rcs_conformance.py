"""The Sinch RCS production configuration, pinned.

This is the owner-supplied specification for WECARE.DIGITAL's live RCS setup, asserted
against the source so a later edit cannot quietly repoint it. Every value here was also
confirmed against the live account on 2026-09-23.

Two things it deliberately protects
-----------------------------------
**The authentication flow.** Live traffic uses the Keycloak password grant against
`auth.aclwhatsapp.com` (Sinch India, formerly ACL Mobile). It is NOT the global Sinch
platform, and it does NOT use a `KEY_ID`/`KEY_SECRET` pair. A well-meaning "upgrade" to
`auth.sinch.com` would point at a different account that does not carry this project, and
the symptom would be a blanket 401 on every send. Measured: 730 sends over 30 days with
**zero** authentication failures, so the current flow is known-good.

**Credentials in Secrets Manager only.** No username, no password, in source or in an
environment variable. The username matters as much as the password here because the
password grant authenticates with the pair, so a hardcoded username is half a credential
in source control - and, worse, a literal default masks a real configuration fault by
turning a missing field into an opaque 401.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "amplify" / "functions" / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

RCS_SEND = ROOT / "amplify" / "functions" / "messaging" / "rcs-send" / "handler.py"
RCS_DLR = ROOT / "amplify" / "functions" / "messaging" / "rcs-dlr" / "handler.py"
SINCH = SHARED / "lambda_utils" / "sinch_rcs.py"

# ---- the specification -----------------------------------------------------
REGION = "us-east-1"
SECRET_ID = "wecare/sinch/rcs"
SECRET_FIELDS = ("username", "password", "project_id", "app_id", "bot_id")

AUTH_URL = ("https://auth.aclwhatsapp.com/realms/ipmessaging/protocol/"
            "openid-connect/token")
CLIENT_ID = "ipmessaging-client"
GRANT_TYPE = "password"
SEND_BASE = "https://convapi.aclwhatsapp.com/v1/projects"

PROJECT_ID = "c8114d03-eeb2-401d-a8f1-abb93594cb33"
APP_ID = "01KQSB792X3R148D8ZGHQYW3SP"
BOT_ID = "69e0b2c980cbf50614ffa5fd"
USERNAME = "wecaretrans"
DEFAULT_TEMPLATE = "rcsmenu"

#: Functions that opt in to RCS with SINCH_RCS_ENABLED=true. Confirmed on the live aliases.
RCS_ENABLED_FUNCTIONS = ("wecare-voice-in-c2c", "wecare-voice-in-obd",
                         "wecare-whatsapp-calling")


def code_only(path: Path) -> str:
    """Source with docstrings and comments stripped.

    Both handlers document the old broken forms in prose so the reason for each change stays
    legible, and a naive substring search would then report the documentation as the defect.
    Comments are blanked in place rather than by rejoining tokens: rejoining splits every
    expression across lines and makes the assertions below unfailable.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    docstring_lines: set = set()
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            docstring_lines.update(
                range(first.lineno, (first.end_lineno or first.lineno) + 1))

    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                if 1 <= row <= len(lines):
                    lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    return "\n".join(line for n, line in enumerate(lines, start=1)
                     if n not in docstring_lines)


class TestAuthenticationFlow:
    """The password grant against Sinch India. Not the global Sinch platform."""

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_token_endpoint(self, path):
        assert AUTH_URL in code_only(path), f"{path.name} must post to {AUTH_URL}"

    @pytest.mark.parametrize("path", [RCS_SEND])
    def test_grant_type_and_client_id(self, path):
        code = code_only(path)
        assert f"'{GRANT_TYPE}'" in code
        assert f"'{CLIENT_ID}'" in code

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_send_endpoint(self, path):
        assert SEND_BASE in code_only(path)

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_not_migrated_to_the_global_sinch_platform(self, path):
        """A different account that does not carry this project. Symptom: blanket 401."""
        code = code_only(path)
        for forbidden in ("auth.sinch.com", "us.conversation.api.sinch.com",
                          "eu.conversation.api.sinch.com", "KEY_ID", "KEY_SECRET",
                          "key_secret"):
            assert forbidden not in code, (
                f"{path.name} references {forbidden}; live RCS authenticates with the "
                "username/password grant against auth.aclwhatsapp.com and migrating is a "
                "separately planned change")


class TestCredentialsComeOnlyFromSecretsManager:
    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_secret_id_is_referenced(self, path):
        assert SECRET_ID in code_only(path)

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_no_password_from_the_environment(self, path):
        code = code_only(path)
        offenders = re.findall(r"(?:environ(?:\.get)?|getenv)\s*[\(\[]\s*['\"]"
                               r"([A-Z0-9_]*(?:PASSWORD|PASSWD|PWD)[A-Z0-9_]*)['\"]", code)
        assert not offenders, f"{path.name} reads a password from the environment: {offenders}"

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_no_username_from_the_environment(self, path):
        """The username is half of the password-grant credential pair."""
        code = code_only(path)
        offenders = re.findall(r"(?:environ(?:\.get)?|getenv)\s*[\(\[]\s*['\"]"
                               r"([A-Z0-9_]*USER(?:NAME)?[A-Z0-9_]*)['\"]", code)
        assert not offenders, f"{path.name} reads a username from the environment: {offenders}"

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_no_literal_username_fallback(self, path):
        """A default username masks a missing field as an opaque 401."""
        code = code_only(path)
        assert f"'{USERNAME}'" not in code, (
            f"{path.name} still falls back to the literal username; that puts half a "
            "credential in source and hides a misconfigured secret")

    @pytest.mark.parametrize("path", [RCS_SEND, SINCH])
    def test_no_literal_bot_id_fallback(self, path):
        code = code_only(path)
        assert f"'{BOT_ID}'" not in code, (
            f"{path.name} still defaults bot_id; after a bot change that would query the "
            "wrong agent and report its templates as ours")

    def test_no_credential_literal_anywhere_in_the_tree(self):
        """Nothing that looks like the password grant's secret half is committed."""
        functions = ROOT / "amplify" / "functions"
        offenders = []
        for path in functions.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"['\"]password['\"]\s*:\s*['\"][^'\"]{6,}['\"]", text):
                offenders.append(str(path.relative_to(functions)))
        assert not offenders, f"literal password value committed in {offenders}"

    def test_sinch_module_loads_every_declared_field(self):
        from lambda_utils import sinch_rcs

        assert tuple(sinch_rcs.SINCH_RCS_FIELDS) == SECRET_FIELDS, (
            "the loader must know every field the secret carries; bot_id was previously "
            "absent here even though the secret held it")
        assert set(sinch_rcs.REQUIRED_FIELDS) == {"username", "password"}

    def test_sinch_module_refuses_an_incomplete_secret(self, monkeypatch):
        """A blank username must fail loudly, not authenticate as a literal."""
        from lambda_utils import sinch_rcs

        class FakeClient:
            def get_secret_value(self, SecretId):  # noqa: N803 - boto3 spelling
                import json as _json
                return {"SecretString": _json.dumps({"password": "x", "app_id": "a"})}

        sinch_rcs._sinch_cache.clear()
        monkeypatch.setattr(sinch_rcs, "_get_secrets_client", lambda: FakeClient())
        assert sinch_rcs._load_sinch_credentials() == {}
        sinch_rcs._sinch_cache.clear()

    def test_sinch_module_loads_a_complete_secret(self, monkeypatch):
        from lambda_utils import sinch_rcs

        class FakeClient:
            def get_secret_value(self, SecretId):  # noqa: N803
                import json as _json
                assert SecretId == SECRET_ID
                return {"SecretString": _json.dumps({
                    "username": USERNAME, "password": "not-a-real-value",
                    "project_id": PROJECT_ID, "app_id": APP_ID, "bot_id": BOT_ID})}

        sinch_rcs._sinch_cache.clear()
        monkeypatch.setattr(sinch_rcs, "_get_secrets_client", lambda: FakeClient())
        creds = sinch_rcs._load_sinch_credentials()
        assert creds["username"] == USERNAME
        assert creds["project_id"] == PROJECT_ID
        assert creds["app_id"] == APP_ID
        assert creds["bot_id"] == BOT_ID
        sinch_rcs._sinch_cache.clear()


class TestNonSecretConfiguration:
    def test_project_and_app_ids_match_the_specification(self):
        code = code_only(RCS_SEND)
        assert PROJECT_ID in code
        assert APP_ID in code

    def test_project_and_app_ids_are_environment_overridable(self):
        """They are non-secret configuration, so they belong in env with a known default."""
        code = code_only(RCS_SEND)
        assert "os.environ.get('RCS_PROJECT_ID'" in code
        assert "os.environ.get('RCS_APP_ID'" in code
        assert "os.environ.get('RCS_SECRET_NAME'" in code

    def test_default_template_is_rcsmenu(self):
        code = code_only(RCS_SEND)
        assert f"'{DEFAULT_TEMPLATE}'" in code
        from lambda_utils import sinch_rcs
        import inspect

        signature = inspect.signature(sinch_rcs.send_rcs_template)
        assert signature.parameters["template_id"].default == DEFAULT_TEMPLATE

    def test_rcs_is_opt_in_and_defaults_off(self):
        from lambda_utils import sinch_rcs

        assert "SINCH_RCS_ENABLED" in code_only(SINCH)
        assert sinch_rcs.is_rcs_enabled() is False, (
            "with the flag unset the sender must be off; it is an opt-in")


class TestRecipientIdentity:
    """India only, and refuse rather than rewrite."""

    def test_indian_forms_are_accepted(self):
        from lambda_utils import sinch_rcs

        for value in ("+919903300044", "919903300044", "9903300044",
                      "09903300044", "+91 99033 00044"):
            assert sinch_rcs._normalize_phone(value) == "919903300044", value

    def test_the_qa_recipient_is_accepted(self):
        from lambda_utils import sinch_rcs

        assert sinch_rcs._normalize_phone("+918100640044") == "918100640044"

    def test_foreign_numbers_are_refused_not_rewritten(self):
        """The defect: several countries are exactly 10 digits in full E.164.

        `+65 8123 4567` used to become `916581234567` - a real and different Indian
        subscriber - and the provider accepted it, so the message reached a stranger with
        nothing reporting a fault.
        """
        from lambda_utils import sinch_rcs

        for value in ("+6581234567", "+14155552671", "+85212345678", "+4512345678"):
            assert sinch_rcs._normalize_phone(value) == "", (
                f"{value} must be refused, never coerced into an Indian identity")

    def test_the_old_rule_is_gone_from_both_senders(self):
        for path in (RCS_SEND, SINCH):
            code = code_only(path)
            assert "'91' + clean[-10:]" not in code
            assert "'91' + clean[-10:]" not in code.replace(" ", "")

    def test_there_is_one_country_authority(self):
        """Both senders defer to lambda_utils.comms.numbers. Two copies is how they drifted."""
        for path in (RCS_SEND, SINCH):
            assert "comms import numbers" in code_only(path), (
                f"{path.name} must use lambda_utils.comms.numbers for country logic")

    def test_empty_and_junk_are_refused(self):
        from lambda_utils import sinch_rcs

        for value in ("", "   ", "12345", "abc"):
            assert sinch_rcs._normalize_phone(value) == ""


class TestSendPayloadShape:
    """The Conversation API body the owner specified."""

    def test_template_send_builds_the_specified_shape(self):
        code = code_only(RCS_SEND)
        for fragment in ("'app_id'", "identified_by", "channel_identities",
                         "'RCS'", "template_message", "channel_template",
                         "template_id", "language_code"):
            assert fragment in code, f"send payload is missing {fragment}"

    def test_identity_carries_no_plus_prefix(self):
        """Sinch Conversation API identity is digits only."""
        from lambda_utils import sinch_rcs

        identity = sinch_rcs._normalize_phone("+919903300044")
        assert identity == "919903300044"
        assert not identity.startswith("+")
