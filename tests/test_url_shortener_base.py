"""The short-link base: what we MINT, and what we must keep HONOURING.

Short links moved from the `r.wecare.digital` subdomain to the `wecare.digital/r`
path on 2026-09-26. The move is only safe because those two questions have
different answers, and this file pins both.

What we mint changed. What we honour did not, and must not: the factory-reset guard
in `operations/system-cleanup` protects ShortLinksTable on the stated grounds that
short links are "printed on materials, embedded in messages, and shared externally".
A link on a printed card cannot be edited, an RCS card already on a handset cannot
be recalled, and the click table held 719 rows when this was written. So the old
host stays mapped, and `SHORT_LINK_BASE` governs generation only.

Resolution is deliberately not asserted here because it is not a property of this
module: the handler accepts `/r/{code}` and a bare `/{code}`, API Gateway maps both
hosts to the same API, and Amplify proxies `/r/<*>`. Those are live-infrastructure
facts, and a unit test claiming to cover them would be asserting its own fixture.
`scripts/check_short_link_hosts.py` probes them for real.
"""
import importlib.util
import os

import pytest

_HANDLER = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'amplify', 'functions', 'core',
    'url-shortener', 'handler.py'))


def _load(monkeypatch, env):
    """Import the handler fresh under a given environment.

    The base is computed at import time, so it cannot be re-read by setting an
    env var on an already-imported module - hence a reload per case.
    """
    for k in ('SHORT_LINK_BASE', 'SHORT_DOMAIN'):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location('url_shortener_base_under_test', _HANDLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_base_is_the_apex_path(monkeypatch):
    """With nothing configured, new links mint on the apex path, not the subdomain."""
    mod = _load(monkeypatch, {})
    assert mod.SHORT_LINK_BASE == 'wecare.digital/r'


def test_short_link_base_env_wins(monkeypatch):
    mod = _load(monkeypatch, {'SHORT_LINK_BASE': 'wecare.digital/r'})
    assert mod.SHORT_LINK_BASE == 'wecare.digital/r'


def test_legacy_short_domain_is_still_honoured_as_a_fallback(monkeypatch):
    """An environment not yet migrated keeps minting its old form rather than
    silently switching. Changing what a deployed function emits should be a
    deliberate env change, not a side effect of shipping code."""
    mod = _load(monkeypatch, {'SHORT_DOMAIN': 'r.wecare.digital'})
    assert mod.SHORT_LINK_BASE == 'r.wecare.digital'


def test_short_link_base_takes_precedence_over_legacy(monkeypatch):
    mod = _load(monkeypatch, {'SHORT_LINK_BASE': 'wecare.digital/r',
                              'SHORT_DOMAIN': 'r.wecare.digital'})
    assert mod.SHORT_LINK_BASE == 'wecare.digital/r'


@pytest.mark.parametrize('raw', ['wecare.digital/r/', ' wecare.digital/r ', '/wecare.digital/r/'])
def test_stray_slashes_and_space_are_normalised(monkeypatch, raw):
    """The built URL is f"https://{base}/{code}". An unnormalised value produces
    `https://wecare.digital/r//abc`, which is a different path from
    `/r/abc` to a static host and would not match the Amplify `/r/<*>` rule."""
    mod = _load(monkeypatch, {'SHORT_LINK_BASE': raw})
    assert mod.SHORT_LINK_BASE == 'wecare.digital/r'
    assert f"https://{mod.SHORT_LINK_BASE}/abc" == 'https://wecare.digital/r/abc'


def test_the_old_host_is_not_treated_as_retired(monkeypatch):
    """Guards against someone copying the `stack.wecare.digital` retirement
    pattern onto this host. That host was removed because it served nothing of its
    own; this one resolves live short codes, so it is an alias, not a redundancy.
    `check_retired_origins.py` must never list it."""
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
    spec = importlib.util.spec_from_file_location(
        'retired_origins_under_test',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts',
                                     'check_retired_origins.py')))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    assert 'r.wecare.digital' not in gate.RETIRED_HOSTS
    # The genuinely dead host stays listed, so this assertion cannot pass by the
    # registry simply being empty.
    assert 'stack.wecare.digital' in gate.RETIRED_HOSTS
