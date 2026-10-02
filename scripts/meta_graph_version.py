"""The Graph base URL for repo scripts, resolved from the central version source.

WHY SCRIPTS NEEDED THEIR OWN RESOLVER
-------------------------------------
`lambda_utils.meta_version` is the single authority for the Graph version, and
`tests/test_meta_version.py` enforces that no handler declares its own. Scripts were outside
that net, and it showed: the 2026-10-01 version audit counted six sources of truth, and a
later review found a **seventh** -- `scripts/meta_webhook_control_plane.py` hard-coding
`v23.0`, two major versions behind the fleet, bypassing the validator entirely. Two more
scripts carried `v25.0` literals.

A script cannot simply import `lambda_utils`: it lives under `amplify/functions/shared`, which
is on no script's path, and a `sys.path` insert in every script is three more things to get
wrong. So this reads `config/vendor-versions.json` -- the generated mirror of
`packages/config/vendorVersions.ts` that `test_meta_version.py` already asserts agrees with the
Python module. Reading a repo file is fine here and is specifically NOT fine in a Lambda, which
is why the Lambda side keeps its own constant: a function should not read a repo file to learn
its own configuration.

The version is validated on the way out, with the same shape rule the module applies, so a
hand-edited mirror cannot put a malformed version into a script's URL.
"""

from __future__ import annotations

import json
import pathlib
import re

#: Same rule as `lambda_utils.meta_version._VERSION_RE`: `vNN.N`, single-digit minor.
_VERSION_RE = re.compile(r"^v\d{1,3}\.\d$")

GRAPH_HOST = "https://graph.facebook.com"

_MIRROR = pathlib.Path(__file__).resolve().parents[1] / "config/vendor-versions.json"


class MetaGraphVersionUnavailable(RuntimeError):
    """The central version source is missing or malformed. Refuses rather than guessing."""


def graph_version() -> str:
    """The Meta Graph version every script should use, from `config/vendor-versions.json`."""
    try:
        value = json.loads(_MIRROR.read_text())["metaGraphApiVersion"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise MetaGraphVersionUnavailable(
            f"cannot read metaGraphApiVersion from {_MIRROR}: {type(error).__name__}. "
            f"Regenerate it with `node scripts/check-versions.ts --write`."
        ) from None
    version = str(value).strip()
    if not _VERSION_RE.match(version):
        raise MetaGraphVersionUnavailable(
            f"metaGraphApiVersion={version!r} is not a Meta Graph version; expected the form "
            f"'v26.0'. Refusing to build a Graph URL from it."
        )
    return version


def graph_base() -> str:
    """`https://graph.facebook.com/<version>`, the base a script should prefix its paths with."""
    return f"{GRAPH_HOST}/{graph_version()}"


__all__ = ["GRAPH_HOST", "MetaGraphVersionUnavailable", "graph_version", "graph_base"]
