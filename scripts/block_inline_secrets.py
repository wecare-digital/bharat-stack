#!/usr/bin/env python3
"""Block shell commands that carry credentials inline. Kiro PreToolUse hook.

Why this exists
---------------
On 2026-09-19 an audit found four live credentials sitting in plaintext inside
Kiro's own workspace permissions file
(``~/.kiro/workspace-roots/<hash>/permissions.yaml``): a Razorpay LIVE key id and
secret, an OpenAI service-account key, a Plivo auth id and token, and a Google
API key. 141 copies of that material were on disk across six files, including an
IDE log with 99 occurrences.

Nobody pasted them into a config on purpose. They arrived because commands were
run with the credential inline::

    RZP_ID='rzp_live_...' RZP_SECRET='...' python3 -c '...'

and when that was approved with "Always allow", Kiro recorded the **entire
command string** as an allow-pattern. The secret became a permission rule.

Rotating the credentials fixes the exposure. This hook fixes the mechanism: it
refuses the command *before* it runs, so there is nothing to record.

What it does
------------
Scans the PreToolUse payload for high-confidence credential shapes. Exit 2 blocks
the tool call and Kiro shows stderr to the agent. Exit 0 allows it.

Deliberately high-precision, not exhaustive. A noisy guard gets disabled, and a
disabled guard protects nothing. It matches issuer-prefixed tokens whose shape is
unambiguous (``rzp_live_``, ``sk-``, ``AIza``, ``ghp_``, ``xoxb-``, AWS
``AKIA``/``ASIA``, private-key PEM headers) plus ``KEY=<20+ char literal>``
assignments. It does NOT try to catch every high-entropy string.

Reference, not a value: pass secrets by reference instead.
    aws secretsmanager ... is gated; prefer
    {{resolve:secretsmanager:wecare/razorpay-webhook:SecretString:key_id}}
    or read them inside the Lambda at runtime, never on a command line.
"""

from __future__ import annotations

import json
import re
import sys

# Each pattern is (label, regex). Anchored on issuer prefixes so the shape alone
# is conclusive; no entropy heuristics, which is what keeps false positives near
# zero.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Razorpay live key id",      re.compile(r"rzp_live_[A-Za-z0-9]{8,}")),
    ("Razorpay test key id",      re.compile(r"rzp_test_[A-Za-z0-9]{8,}")),
    ("OpenAI key",                re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}")),
    ("Anthropic key",             re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Google API key",            re.compile(r"\bAIza[A-Za-z0-9_\-]{30,}")),
    ("GitHub token",              re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token",               re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("AWS access key id",         re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Stripe secret key",         re.compile(r"\bsk_live_[A-Za-z0-9]{20,}")),
    ("Twilio auth token",         re.compile(r"\bSK[0-9a-fA-F]{32}\b")),
    ("private key PEM",           re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    # Inline assignment of a long literal to a secret-ish name. Requires quotes
    # and 20+ chars so `FOO=bar` and `PORT=5476` never trip it.
    ("inline secret assignment",  re.compile(
        r"\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY|AUTH_TOKEN|"
        r"ACCESS_KEY|PRIVATE_KEY|CLIENT_SECRET)[A-Z0-9_]*\s*=\s*"
        r"['\"][^'\"]{20,}['\"]")),
]

# Referencing a secret by NAME is the correct pattern and must stay allowed, even
# though such commands contain the word "secret".
ALLOWLIST = [
    re.compile(r"\{\{resolve:secretsmanager:"),          # CloudFormation dynamic ref
    re.compile(r"SecretId\s*=\s*['\"]?wecare/"),         # boto3 by-name lookup
    re.compile(r"--secret-id\s+wecare/"),                # CLI by-name lookup
    re.compile(r"[A-Z0-9_]*SECRET[A-Z0-9_]*\s*=\s*['\"]?wecare/"),  # name, not value
]


def extract_text(payload: object) -> str:
    """Flatten the whole payload to text.

    Deliberately schema-agnostic: the hook contract may nest the command under
    different keys across versions, and a guard that silently stops matching
    after an upgrade is worse than one that over-reads.
    """
    return json.dumps(payload) if not isinstance(payload, str) else payload


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0

    try:
        haystack = extract_text(json.loads(raw))
    except json.JSONDecodeError:
        haystack = raw

    # Unescape so JSON-encoded quotes still match the assignment pattern.
    haystack = haystack.replace('\\"', '"').replace("\\'", "'")

    if any(a.search(haystack) for a in ALLOWLIST):
        return 0

    hits = sorted({label for label, rx in PATTERNS if rx.search(haystack)})
    if not hits:
        return 0

    print(
        "BLOCKED: this command appears to contain a credential inline: "
        + ", ".join(hits)
        + ".\n"
        "Inline credentials get recorded verbatim into Kiro's permissions file "
        "when approved with 'Always allow' - that is how four live keys leaked "
        "on 2026-09-19.\n"
        "Pass the secret by reference instead: read it inside the function from "
        "Secrets Manager by NAME (e.g. SecretId='wecare/razorpay-webhook'), or "
        "use {{resolve:secretsmanager:<name>:SecretString:<json-key>}}. "
        "Never put the value on a command line.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
