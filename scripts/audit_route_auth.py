#!/usr/bin/env python3
"""Find HTTP API routes that are open at BOTH the gateway and the handler.

Why this exists
---------------
On 2026-09-20, while removing Airtel, three routes were found by accident:

    POST   /voice-cdr-webhook              AuthorizationType=NONE
    GET    /voice-cdr-webhook              AuthorizationType=NONE
    DELETE /voice-cdr-webhook/clear-logs   AuthorizationType=NONE

Their handler contained no `require_auth` either, so they were reachable by
anyone. That allowed a forged CDR to fan out WhatsApp and SMS to two hardcoded
admin numbers, an arbitrary `recordingURL` to be fetched server-side and written
into S3 (SSRF plus arbitrary upload), and every call detail record to be wiped.

Three were found by accident out of 331 routes. This script checks the rest.

What "open" means here
----------------------
`AuthorizationType=NONE` on its own is NOT a finding. Most of this API
authenticates inside the Lambda via `lambda_utils.middleware.require_auth`, and
provider webhooks authenticate by signature (Plivo V3, Razorpay HMAC, Meta
X-Hub-Signature) which cannot be expressed as an API Gateway authorizer.

A route is reported OPEN only when the gateway does not authorize it AND its
handler shows no evidence of authenticating: no `require_auth`, no signature
verification, no shared-secret comparison.

Confidence is deliberately limited: this greps handler source for auth markers,
so a handler that authenticates by some means not in MARKERS will be reported as
a false positive. Read the finding before acting on it. Silence is not proof of
safety either - an unused marker name would hide a real hole.

Usage
-----
    python scripts/audit_route_auth.py            # report
    python scripts/audit_route_auth.py --gate     # exit 1 if any OPEN route

Exit codes
----------
    0  no OPEN routes, or report mode
    1  at least one OPEN route (only with --gate)
    2  could not query AWS
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("boto3 required", file=sys.stderr)
    raise SystemExit(2)

REGION = "us-east-1"
HTTP_API_ID = "zllr9lrg7j"
REPO = pathlib.Path(__file__).resolve().parents[1]
FUNCTIONS_ROOT = REPO / "amplify/functions"

# Evidence that a handler authenticates its caller somehow. Deliberately broad:
# a false NEGATIVE here (missing a real auth mechanism) produces a false alarm,
# which is cheap. A false POSITIVE marks a hole as safe, which is not.
MARKERS = (
    "require_auth",            # lambda_utils.middleware, Cognito JWT
    "require_role",
    "verify_signature",
    "_verify_provider",        # plivo-answer signature/trust ladder
    "plivo_signature",
    "X-Razorpay-Signature",
    "x-hub-signature",
    "X-Hub-Signature",
    "hmac.compare_digest",
    "compare_digest",
    "appsecret_proof",
    "verify_token",
    "VERIFY_TOKEN",
    "shared_secret",
    "SHARED_SECRET",
    "api_key",
    "API_KEY",
    "Authorization",
)

# Routes intentionally reachable without a caller identity. Each needs a reason.
EXPECTED_PUBLIC = {
    "OPTIONS": "CORS preflight; carries no data and must not require auth",
}


def handler_sources() -> dict[str, str]:
    """Map lambda function name -> concatenated source of its directory."""
    out: dict[str, str] = {}
    for handler in FUNCTIONS_ROOT.rglob("handler.py"):
        if "__pycache__" in str(handler):
            continue
        # amplify/functions/messaging/outbound-sms/handler.py -> outbound-sms
        slug = handler.parent.name
        parent = handler.parent.parent.name
        text = ""
        for f in handler.parent.rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                text += f.read_text(errors="replace")
            except OSError:
                pass
        # register under several plausible deployed names
        for key in {f"wecare-{slug}", f"wecare-{parent}-{slug}",
                    f"stack-wecare-{slug}"}:
            out.setdefault(key, "")
            out[key] += text
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate", action="store_true")
    args = ap.parse_args()

    api = boto3.client("apigatewayv2", region_name=REGION)
    try:
        routes, token, pages = [], None, 0
        while True:
            kw = {"ApiId": HTTP_API_ID, "MaxResults": "100"}
            if token:
                kw["NextToken"] = token
            r = api.get_routes(**kw)
            routes += r["Items"]
            pages += 1
            token = r.get("NextToken")
            if not token:
                break
        integrations = {}
        token = None
        while True:
            kw = {"ApiId": HTTP_API_ID, "MaxResults": "100"}
            if token:
                kw["NextToken"] = token
            r = api.get_integrations(**kw)
            for i in r["Items"]:
                integrations[i["IntegrationId"]] = i.get("IntegrationUri", "")
            token = r.get("NextToken")
            if not token:
                break
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read API: {type(exc).__name__}", file=sys.stderr)
        return 2

    sources = handler_sources()
    print(f"routes       : {len(routes)} across {pages} page(s)")
    print(f"integrations : {len(integrations)}")
    print(f"handler dirs : {len(sources)}\n")

    open_routes, gw_none_handler_ok, authorized, unknown = [], 0, 0, []

    for rt in sorted(routes, key=lambda x: x["RouteKey"]):
        key = rt["RouteKey"]
        method = key.split()[0]
        if rt.get("AuthorizationType") not in (None, "NONE"):
            authorized += 1
            continue
        if method in EXPECTED_PUBLIC:
            continue

        target = (rt.get("Target") or "").split("/")[-1]
        uri = integrations.get(target, "")
        fn = ""
        m = re.search(r"function:([A-Za-z0-9\-_]+)", uri)
        if m:
            fn = m.group(1)

        src = sources.get(fn, "")
        if not src:
            unknown.append((key, fn or "<unresolved>"))
            continue
        if any(mk in src for mk in MARKERS):
            gw_none_handler_ok += 1
        else:
            open_routes.append((key, fn))

    print(f"gateway-authorized            : {authorized}")
    print(f"gateway NONE, handler authenticates : {gw_none_handler_ok}")
    print(f"handler source not resolvable : {len(unknown)}")
    print(f"OPEN (no auth at either layer): {len(open_routes)}\n")

    if open_routes:
        print("OPEN ROUTES - reachable by anyone:")
        for key, fn in open_routes:
            print(f"  {key:44} -> {fn}")
        print()
    if unknown:
        print("UNRESOLVED - could not find handler source, verify by hand:")
        for key, fn in unknown[:40]:
            print(f"  {key:44} -> {fn}")
        if len(unknown) > 40:
            print(f"  ... {len(unknown) - 40} more")

    if open_routes and args.gate:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
