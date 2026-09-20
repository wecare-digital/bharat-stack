#!/usr/bin/env python3
"""Ensure POST /plivo/dial-events exists and the alias may be invoked for it.

Why this exists
---------------
The connected-call notification work (Phase 8, commit b23e585e) was built,
tested and deployed, and never ran once. Two things were missing in the account,
neither of them in code:

  1. There was no ``POST /plivo/dial-events`` route on HTTP API zllr9lrg7j. The
     answer XML emits ``<Dial callbackUrl=".../plivo/dial-events">``, so every
     connected-call callback Plivo sent got a 404.
  2. After adding the route it returned 500, not 401. The Lambda was never
     invoked - no log line at all - because this API grants
     ``lambda:InvokeFunction`` **per route** on the ``live`` alias, and there was
     no statement for the new route. API Gateway got AccessDenied and surfaced it
     as a 500.

Both are easy to miss because neither shows up as a failing test or a failed
deploy. It looked shipped.

Worth knowing: a Plivo *application* has only Answer, Hangup, Fallback and
Message URLs. ``callbackUrl`` is a per-call attribute of the ``<Dial>`` verb, not
an application setting, so there is nothing to register at Plivo for this. The
missing piece was always on our side.

Verification, in order of usefulness
------------------------------------
    404  route does not exist
    500  route exists, alias permission missing (Lambda never invoked)
    401  CORRECT - reached the handler, refused for a missing signature

Usage
-----
    python scripts/ensure_plivo_dial_events_route.py            # report
    python scripts/ensure_plivo_dial_events_route.py --apply    # converge

Idempotent: re-running when both exist changes nothing.
"""

from __future__ import annotations

import argparse
import sys

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("boto3 required", file=sys.stderr)
    raise SystemExit(2)

REGION = "us-east-1"
API_ID = "zllr9lrg7j"
ACCOUNT = "775261844268"
ROUTE_KEY = "POST /plivo/dial-events"
# Copy the integration from this route: same Lambda, same :live alias.
TEMPLATE_ROUTE = "POST /plivo/events"
FUNCTION = "wecare-plivo-answer"
ALIAS = "live"
STATEMENT_ID = "apigw-plivo-dial-events"
SOURCE_ARN = (f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}"
              "/*/POST/plivo/dial-events")


def all_routes(api):
    out, token = [], None
    while True:
        kw = {"ApiId": API_ID, "MaxResults": "100"}
        if token:
            kw["NextToken"] = token
        r = api.get_routes(**kw)
        out += r["Items"]
        token = r.get("NextToken")
        if not token:
            return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    try:
        routes = all_routes(api)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read API: {type(exc).__name__}", file=sys.stderr)
        return 2

    by_key = {r["RouteKey"]: r for r in routes}
    have_route = ROUTE_KEY in by_key
    print(f"route {ROUTE_KEY!r}: {'present' if have_route else 'MISSING'}")

    import json
    have_perm = False
    try:
        pol = json.loads(lam.get_policy(FunctionName=FUNCTION,
                                        Qualifier=ALIAS)["Policy"])
        have_perm = any(
            s.get("Condition", {}).get("ArnLike", {}).get("AWS:SourceArn", "")
            == SOURCE_ARN for s in pol["Statement"])
    except ClientError:
        pass
    print(f"alias {ALIAS!r} invoke permission for that route: "
          f"{'present' if have_perm else 'MISSING'}")

    if have_route and have_perm:
        print("\nnothing to do. Probe should return 401 (signature required):")
        print(f"  curl -X POST https://api.wecare.digital/plivo/dial-events "
              "-d 'CallUUID=probe'")
        return 0

    if not args.apply:
        print("\nre-run with --apply to converge.")
        return 1

    if not have_route:
        tmpl = by_key.get(TEMPLATE_ROUTE)
        if not tmpl:
            print(f"cannot find {TEMPLATE_ROUTE!r} to copy the integration from",
                  file=sys.stderr)
            return 2
        r = api.create_route(ApiId=API_ID, RouteKey=ROUTE_KEY,
                             Target=tmpl["Target"])
        print(f"  created {ROUTE_KEY} -> {tmpl['Target']} "
              f"(routeId {r['RouteId']})")

    if not have_perm:
        try:
            lam.add_permission(
                FunctionName=FUNCTION, Qualifier=ALIAS,
                StatementId=STATEMENT_ID, Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com", SourceArn=SOURCE_ARN)
            print(f"  added {STATEMENT_ID} on alias {ALIAS}")
        except lam.exceptions.ResourceConflictException:
            print(f"  {STATEMENT_ID} already present")

    print("\nconverged. Verify (expect 401, NOT 404 or 500):")
    print("  curl -o /dev/null -w '%{http_code}\\n' -X POST "
          "https://api.wecare.digital/plivo/dial-events -d 'CallUUID=probe'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
