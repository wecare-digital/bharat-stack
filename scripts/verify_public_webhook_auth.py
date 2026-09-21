#!/usr/bin/env python3
"""Live check: the two public webhook ingresses reject unauthenticated callers.

This is the deployed counterpart to tests/test_public_webhook_auth.py. Unit tests
prove the handler logic; this proves the deployed alias actually enforces it,
which a green test suite cannot.

Every probe is deliberately inert
---------------------------------
  POST /whatsapp/inbound      unsigned, body {}    expect 401
  POST /webhook/sinch-rcs     unsigned, INBOUND    expect 503
  GET  /webhook/sinch-rcs     unsigned             expect 200 (health)

The inbound-shaped Sinch body is the exploit payload: before 2026-09-21 it wrote
a forged message into the canonical MessagesTable and could trigger an outbound
RCS send. It is safe to send now precisely because the fix refuses it before any
parsing or side effect - if this script ever reports 200 for that probe, the
protection has regressed.

Deliberately NOT probed: an unsigned MESSAGE_DELIVERY body. While no webhook
secret is configured at Sinch that type is still processed by design, and
`_process_delivery` issues a DynamoDB update_item, which upserts - so a probe
with a synthetic message id would write a junk row into MessagesTable. Unit
tests cover that path instead.

No credential is sent, because these endpoints require none. That is the point.

    python scripts/verify_public_webhook_auth.py
    python scripts/verify_public_webhook_auth.py --gate   # exit 1 on any mismatch
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

BASE = "https://api.wecare.digital"
TIMEOUT = 20

# (label, method, path, body, expected status, why)
PROBES = [
    ("whatsapp inbound, unsigned", "POST", "/whatsapp/inbound", {}, 401,
     "no X-Hub-Signature-256; must not reach the SNS-envelope parser"),
    ("whatsapp inbound, unsigned create_invoice", "POST", "/whatsapp/inbound",
     {"action": "create_invoice", "contactId": "probe"}, 401,
     "the internal-only branch must not be reachable over HTTP"),
    ("sinch rcs, unsigned MESSAGE_INBOUND", "POST", "/webhook/sinch-rcs",
     {"message": {"contact_message": {"text_message": {"text": "probe"}},
                  "channel_identity": {"channel": "RCS", "identity": "+910000000000"}}},
     503, "forged inbound must be refused before MessagesTable or rcs-send"),
    ("sinch rcs health", "GET", "/webhook/sinch-rcs", None, 200,
     "the health path stays reachable"),
]


# Build one opener with proxies explicitly disabled. urllib otherwise consults
# the system proxy configuration, and on this machine an unset-but-present macOS
# proxy lookup made the first request hang past a 180s budget while the identical
# curl call returned in under a second.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def probe(method: str, path: str, body) -> tuple[int, str]:
    data = None
    headers = {"user-agent": "wecare-auth-verifier/1.0",
               "connection": "close"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["content-type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers,
                                 method=method)
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read(400).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(400).decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, f"transport error: {type(exc).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any probe does not match its expectation")
    args = ap.parse_args()

    print(f"target {BASE}\n")
    failures = 0
    for label, method, path, body, expected, why in PROBES:
        status, snippet = probe(method, path, body)
        ok = status == expected
        if not ok:
            failures += 1
        mark = "ok  " if ok else "FAIL"
        print(f"  {mark} {label}")
        print(f"       {method} {path} -> {status} (expected {expected})")
        print(f"       {why}")
        if not ok:
            print(f"       body: {snippet.strip()[:200]}")
        print()

    print(f"{len(PROBES) - failures}/{len(PROBES)} probes as expected")
    if failures:
        print("\nA mismatch here means the deployed alias is not enforcing what "
              "the unit tests assert. Check that `live` points at the version "
              "carrying the fix.")
    return 1 if (failures and args.gate) else 0


if __name__ == "__main__":
    raise SystemExit(main())
