"""The Wix credential secret name must agree across every place that names it.

The defect
----------
`scripts/set_wix_credential.py` carried `SECRET_NAME = "wecare/wix/headless"` while both
`src/config/wix.ts` and the secret that actually exists in account 775261844268 use
`wecare/wix/headless-api-key`. Nothing crashed, which is why it survived: the name is only
ever passed to AWS, so the failure surfaced as

  * `--status` reporting `exists: false` for a secret that was present, and
  * `--set-env` pointing the live Lambda at a secret that does not exist, whereupon
    `wix-store`'s `_load_wix_api_key` raises `RuntimeError` on every Wix call.

Both look like "the key is missing" rather than "the tool is looking in the wrong place",
which sends the next person to re-mint a credential they already have. A single-source
string compared in a test is cheaper than that diagnosis.

These tests read the source text rather than importing the script, because
`set_wix_credential` constructs boto3 clients and the point is to pin the literal.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "set_wix_credential.py"
TS_CONFIG = REPO / "src" / "config" / "wix.ts"
HANDLER = REPO / "amplify" / "functions" / "ecommerce" / "wix-store" / "handler.py"

EXPECTED = "wecare/wix/headless-api-key"


def _script_secret_name() -> str:
    match = re.search(
        r'^SECRET_NAME\s*=\s*["\']([^"\']+)["\']',
        SCRIPT.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match, "SECRET_NAME assignment not found in set_wix_credential.py"
    return match.group(1)


def _ts_secret_name() -> str:
    match = re.search(
        r'WIX_API_KEY_SECRET\s*=\s*["\']([^"\']+)["\']',
        TS_CONFIG.read_text(encoding="utf-8"),
    )
    assert match, "WIX_API_KEY_SECRET not found in src/config/wix.ts"
    return match.group(1)


def test_provisioning_script_and_frontend_config_agree() -> None:
    """The two places that name the secret must name the same secret."""
    assert _script_secret_name() == _ts_secret_name() == EXPECTED


def test_script_does_not_use_the_name_that_never_existed() -> None:
    """`wecare/wix/headless` is not a secret in this account and never has been."""
    assert _script_secret_name() != "wecare/wix/headless"


def test_handler_resolves_the_secret_name_from_the_environment() -> None:
    """The Lambda must take the name from env, not hardcode it.

    Two names in two languages is already one too many. A third, compiled into the
    function package, could only be corrected by a redeploy.
    """
    source = HANDLER.read_text(encoding="utf-8")
    assert "WIX_API_KEY_SECRET = os.environ.get('WIX_API_KEY_SECRET', '')" in source
    assert EXPECTED not in source, (
        "the handler should reference the secret by env var, not embed its name"
    )


def test_handler_has_no_environment_fallback_for_the_key_itself() -> None:
    """The key must come from Secrets Manager only.

    An earlier docstring in the handler claimed "env as migration fallback", which invited
    someone to put a plaintext credential in a Lambda environment variable and expect it to
    work. The loader raises instead, and that is the behaviour worth pinning.
    """
    source = HANDLER.read_text(encoding="utf-8")
    assert "Wix Headless API credentials are not configured" in source
    for plaintext_env in ("os.environ.get('WIX_API_KEY'", 'os.environ.get("WIX_API_KEY"'):
        assert plaintext_env not in source, (
            "the API key value must never be read from an environment variable"
        )


@pytest.mark.parametrize("flag", ["--client-secret", "--verify-oauth"])
def test_script_supports_the_recommended_oauth_mechanism(flag: str) -> None:
    """Wix documents client_credentials as the recommended admin mechanism.

    The script has to be able to store and prove a client secret, or the migration off the
    permanent API key has no tooling and will not happen.
    """
    assert flag in SCRIPT.read_text(encoding="utf-8")


def test_script_refuses_to_store_no_credential() -> None:
    """Storing only the non-secret ids would look like success and authenticate nothing."""
    assert "that would store no credential at all" in SCRIPT.read_text(encoding="utf-8")
