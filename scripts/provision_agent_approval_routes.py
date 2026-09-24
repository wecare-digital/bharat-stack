#!/usr/bin/env python3
"""Register the agent approval routes on HTTP API zllr9lrg7j.

    POST /ai/approvals          record an operator's yes to one exact plan
    POST /ai/approvals/status   report an approval without consuming it

Both land on the existing `wecare-ai-generate-response:live` integration, the same
one behind `POST /ai/generate`. A second integration to the same alias would be two
places to change when the alias moves.

Why these are separate routes rather than another field in the /ai/generate body
-------------------------------------------------------------------------------
`/ai/generate` requires a signed-in user. The approve path requires an Admin with an
enrolled second factor. One handler entry point serving two privilege levels means
one `require_auth` call trying to express both, and in that arrangement the looser
one wins by default. Separate route keys also mean the two can be given different
authorizers later, and that an approval shows up as its own line in an access log.

The permission gotcha, recorded because it cost a silent outage before
---------------------------------------------------------------------
This API grants `lambda:InvokeFunction` per route on some functions. When
`POST /plivo/dial-events` was added without a matching statement, API Gateway got
AccessDenied and returned 500 - with no Lambda log line at all, because the function
was never invoked. It looked deployed.

`wecare-ai-generate-response:live` already carries a WILDCARD statement
(`apigw-snapstart-live` on `zllr9lrg7j/*/*`), so no new permission is needed here.
That is verified rather than assumed: `--verify` reads the policy and says which
statement covers the new routes.

Verification ladder, in order of usefulness:

    404  route does not exist
    500  route exists, alias invoke permission missing
    401  route exists, handler reached, refused for no token   <- CORRECT
    403  reached and refused for insufficient role

401 is the pass. A 200 from an unauthenticated probe would mean the Admin gate is
not doing its job.

Usage:
    python scripts/provision_agent_approval_routes.py            # report
    python scripts/provision_agent_approval_routes.py --apply
    python scripts/provision_agent_approval_routes.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
API_ID = "zllr9lrg7j"
ACCOUNT = "775261844268"
FUNCTION = "wecare-ai-generate-response"
ALIAS = "live"

# Copy the integration from this route: same function, same alias, same payload
# format. Reading it live rather than hardcoding the integration id means an alias
# or integration change cannot leave these routes pointing somewhere stale.
TEMPLATE_ROUTE = "POST /ai/generate"

ROUTE_KEYS = ("POST /ai/approvals", "POST /ai/approvals/status")

BASE_URL = "https://api.wecare.digital"


def all_routes(api):
    items, token = [], None
    while True:
        kw = {"ApiId": API_ID, "MaxResults": "100"}
        if token:
            kw["NextToken"] = token
        page = api.get_routes(**kw)
        items += page.get("Items", [])
        token = page.get("NextToken")
        if not token:
            return items


def alias_permission_covers(lam) -> str:
    """Which policy statement lets API Gateway invoke the alias for these routes.

    Returns the Sid, or '' if nothing covers them. A per-route statement would only
    match its own path, so a wildcard is what makes a newly added route work without
    a second call.
    """
    try:
        policy = json.loads(lam.get_policy(FunctionName=FUNCTION,
                                           Qualifier=ALIAS)["Policy"])
    except ClientError:
        return ""
    for statement in policy.get("Statement", []):
        arn = (statement.get("Condition", {}).get("ArnLike", {})
               .get("AWS:SourceArn", ""))
        if not arn.startswith(f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}"):
            continue
        # `/*/*` and `/*/*/*` both cover any method and path on this API.
        tail = arn.split(f"{API_ID}", 1)[1]
        if tail.strip("/").replace("/", "") == "*" * len(
                [p for p in tail.strip("/").split("/") if p]):
            return statement.get("Sid", "(unnamed)")
    return ""


def probe(path: str) -> str:
    """Unauthenticated POST. Returns the status code as a string, or an error name.

    Inert on the success path: no token means the Admin gate refuses before anything
    is read or written, which is exactly what is being confirmed.
    """
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return str(response.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}"


def report(api, lam) -> dict:
    by_key = {r["RouteKey"]: r for r in all_routes(api)}
    state = {
        "template": by_key.get(TEMPLATE_ROUTE, {}).get("Target", ""),
        "routes": {k: by_key.get(k, {}).get("RouteId", "") for k in ROUTE_KEYS},
        "permission_sid": alias_permission_covers(lam),
    }
    print(f"api: {API_ID}")
    print(f"template {TEMPLATE_ROUTE} -> {state['template'] or 'MISSING'}")
    for key, route_id in state["routes"].items():
        print(f"  {key}: {'routeId ' + route_id if route_id else 'MISSING'}")
    print(f"alias invoke permission: "
          f"{state['permission_sid'] or 'MISSING (routes would return 500)'}")
    return state


def apply(api, state) -> int:
    target = state["template"]
    if not target:
        print(f"cannot find {TEMPLATE_ROUTE!r} to copy the integration from",
              file=sys.stderr)
        return 2

    created = 0
    for key, route_id in state["routes"].items():
        if route_id:
            print(f"  {key} already present")
            continue
        made = api.create_route(ApiId=API_ID, RouteKey=key, Target=target)
        print(f"  created {key} -> {target} (routeId {made['RouteId']})")
        created += 1

    if not state["permission_sid"]:
        print("  alias has no wildcard invoke statement; these routes will return "
              "500 until one exists", file=sys.stderr)
        return 2

    print(f"\n{created} route(s) created")
    return 0


def verify() -> int:
    problems = []
    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    state = report(api, lam)

    for key, route_id in state["routes"].items():
        if not route_id:
            problems.append(f"{key} does not exist")
    if not state["permission_sid"]:
        problems.append("no wildcard alias invoke permission")

    print("\nunauthenticated probes (401 or 403 is the pass):")
    for path in ("/ai/approvals", "/ai/approvals/status"):
        code = probe(path)
        print(f"  POST {path} -> {code}")
        if code == "404":
            problems.append(f"POST {path} returned 404; the route is not live")
        elif code == "500":
            problems.append(f"POST {path} returned 500; the alias invoke "
                            f"permission is missing and the Lambda was never called")
        elif code == "200":
            problems.append(f"POST {path} returned 200 WITHOUT a token; the Admin "
                            f"gate is not refusing anonymous callers")
        elif code not in ("401", "403"):
            problems.append(f"POST {path} returned {code}, expected 401 or 403")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\napproval routes live and refusing unauthenticated callers")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    try:
        state = report(api, lam)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read the API: {type(exc).__name__}", file=sys.stderr)
        return 2

    if all(state["routes"].values()) and state["permission_sid"]:
        print("\nnothing to do; run --verify to probe them")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1
    return apply(api, state)


if __name__ == "__main__":
    raise SystemExit(main())
