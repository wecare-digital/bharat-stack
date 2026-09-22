"""`AUTH_SKIP_PATHS` must exempt a path, not a substring.

What was measured
-----------------
`wecare-whatsapp-business-api` was deployed with
`AUTH_SKIP_PATHS="/wa-business/webhooks,/wa-business/flow-data"` and `require_auth`
matched with `skip.strip() in path` - a bare substring test. Probed
unauthenticated against production on 2026-09-21:

    GET /wa-business/webhooks   ->  400 {"error": "wabaId required"}   past auth
    GET /wa-business/profile    ->  401 {"error": "No authorization token provided"}

`/wa-business/webhooks` is not a Meta callback. It is the management surface for
Meta's `subscribed_apps` API: `DELETE` unsubscribes the WABA from every webhook
field (stopping all inbound WhatsApp delivery) and `POST` forwards
`override_callback_uri` to Meta (repointing production webhooks at a caller-chosen
URL). Neither required a token.

Two loose matchers compounded it. The function also serves
`ANY /wa-business/{proxy+}`, so `/wa-business/webhooks-anything` reached the same
handler, satisfied the substring skip, and then satisfied the handler's own
`elif '/webhooks' in path` dispatch.

`/wa-business/flow-data` stays exempt and is genuinely self-authenticating: the
Flows data-exchange payload is RSA+AES-GCM encrypted, so only a caller holding our
public key can produce something we can decrypt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'amplify' / 'functions' / 'shared'
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

with patch('boto3.client', MagicMock()):
    from lambda_utils import middleware

FLOW_DATA = '/wa-business/flow-data'
WEBHOOKS = '/wa-business/webhooks'


@pytest.fixture
def skips(monkeypatch):
    """Install a skip list, as the deployed env var would."""
    def _install(*paths):
        monkeypatch.setattr(middleware, 'AUTH_SKIP_PATHS', list(paths))
    return _install


class TestSegmentBoundaries:
    def test_exact_match_is_exempt(self, skips):
        skips(FLOW_DATA)
        assert middleware.path_is_exempt(FLOW_DATA) is True

    def test_trailing_slash_is_exempt(self, skips):
        skips(FLOW_DATA)
        assert middleware.path_is_exempt(FLOW_DATA + '/') is True

    def test_child_segment_is_exempt(self, skips):
        """A provider may append a sub-path; the endpoint still self-authenticates."""
        skips(FLOW_DATA)
        assert middleware.path_is_exempt(FLOW_DATA + '/v2') is True

    @pytest.mark.parametrize('path', [
        '/wa-business/flow-dataX',
        '/wa-business/flow-data-admin',
        '/wa-business/flow-datax/delete',
        '/x/wa-business/flow-data',
        '/wa-business/profile?next=/wa-business/flow-data',
    ])
    def test_near_miss_is_not_exempt(self, skips, path):
        """These all satisfied `skip in path` and therefore skipped auth. Each is
        reachable through the `ANY /wa-business/{proxy+}` catch-all."""
        skips(FLOW_DATA)
        assert middleware.path_is_exempt(path) is False

    def test_stage_prefix_does_not_defeat_the_match(self, skips):
        """The custom-domain mapping puts the stage in the path on this API, which
        has already broken routing twice (see `lambda_utils.http_path`). A
        stage-prefixed request to a genuinely exempt endpoint must stay exempt."""
        skips(FLOW_DATA)
        assert middleware.path_is_exempt('/prod' + FLOW_DATA, 'prod') is True
        assert middleware.path_is_exempt(FLOW_DATA, 'prod') is True

    def test_stage_stripping_does_not_widen_the_match(self, skips):
        skips(FLOW_DATA)
        assert middleware.path_is_exempt('/prod' + FLOW_DATA + 'X', 'prod') is False
        # A different stage name is not stripped, so the path does not match.
        assert middleware.path_is_exempt('/prod' + FLOW_DATA, 'staging') is False

    def test_empty_skip_list_exempts_nothing(self, skips):
        skips('')
        assert middleware.path_is_exempt(FLOW_DATA) is False
        assert middleware.path_is_exempt('/anything') is False

    def test_no_skip_config_exempts_nothing(self, skips):
        skips()
        assert middleware.path_is_exempt('/') is False
        assert middleware.path_is_exempt('') is False

    def test_a_bare_slash_skip_entry_no_longer_exempts_everything(self, skips):
        """`AUTH_SKIP_PATHS="/"` used to exempt every route on the function,
        because every path contains '/'. Under segment matching it exempts only
        the root."""
        skips('/')
        assert middleware.path_is_exempt('/wa-business/profile') is False
        assert middleware.path_is_exempt('/wa-business/webhooks') is False
        assert middleware.path_is_exempt('/') is True


class TestTheWebhooksRouteIsNoLongerExempt:
    """The live configuration after this change: flow-data only."""

    DEPLOYED = [FLOW_DATA]

    @pytest.mark.parametrize('path', [
        WEBHOOKS, WEBHOOKS + '/', '/wa-business/webhooks-anything',
    ])
    def test_webhooks_management_requires_auth(self, skips, path):
        skips(*self.DEPLOYED)
        assert middleware.path_is_exempt(path) is False

    def test_flow_data_still_exempt(self, skips):
        skips(*self.DEPLOYED)
        assert middleware.path_is_exempt(FLOW_DATA) is True

    def test_the_manifest_matches_this_expectation(self):
        """The deployed value and the manifest must not drift apart, or the next
        `deploy env` run silently reopens the hole."""
        import json
        manifest = json.loads((ROOT / 'config' / 'lambda-env-manifest.json').read_text())
        env = None
        for key in ('functions', 'Functions'):
            if isinstance(manifest.get(key), dict):
                env = manifest[key].get('wecare-whatsapp-business-api')
                break
        if env is None:
            env = manifest.get('wecare-whatsapp-business-api')
        assert env is not None, 'wecare-whatsapp-business-api missing from the manifest'
        value = env.get('AUTH_SKIP' + '_PATHS', '')
        entries = [e.strip() for e in value.split(',') if e.strip()]
        assert entries == [FLOW_DATA], (
            f'AUTH_SKIP_PATHS should contain only {FLOW_DATA}, found {entries}')


class TestRequireAuthUsesIt:
    """End-to-end through `require_auth`, so the wiring is pinned too."""

    def _event(self, path, token=None):
        headers = {'authorization': f'Bearer {token}'} if token else {}
        return {
            'requestContext': {'apiId': 'zllr9lrg7j', 'domainName': 'api.wecare.digital',
                               'http': {'method': 'GET', 'path': path, 'sourceIp': '1.2.3.4'}},
            'headers': headers,
        }

    def test_exempt_path_skips_auth(self, skips):
        skips(FLOW_DATA)
        assert middleware.require_auth(self._event(FLOW_DATA)) is None

    def test_webhooks_now_gets_401(self, skips):
        skips(FLOW_DATA)
        result = middleware.require_auth(self._event(WEBHOOKS))
        assert result is not None
        assert result['statusCode'] == 401

    def test_near_miss_now_gets_401(self, skips):
        skips(FLOW_DATA)
        result = middleware.require_auth(self._event('/wa-business/flow-dataX'))
        assert result is not None
        assert result['statusCode'] == 401

    def test_internal_invoke_is_still_exempt(self, skips):
        """No API Gateway context means a direct Lambda invoke, which already
        requires IAM. This must keep working or every internal call breaks."""
        skips(FLOW_DATA)
        assert middleware.require_auth({'headers': {}, 'body': '{}'}) is None

    def test_options_preflight_is_still_exempt(self, skips):
        skips(FLOW_DATA)
        event = self._event(WEBHOOKS)
        event['requestContext']['http']['method'] = 'OPTIONS'
        assert middleware.require_auth(event) is None
