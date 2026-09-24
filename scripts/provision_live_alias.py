#!/usr/bin/env python3
"""Put a function behind a `live` alias and repoint its API routes at it.

The gap this closes
-------------------
The runtime inventory reports 25 routes whose integration URI is an **unqualified**
function ARN, so API Gateway invokes `$LATEST`. Those routes bypass the version and
alias model the rest of the fleet uses, which costs two things:

* **No rollback.** Moving an alias back one version is a single call. Undoing an
  `update-function-code` means rebuilding and re-uploading the previous package, and
  the previous package may no longer exist anywhere.
* **No atomic cutover.** `$LATEST` changes the instant the upload finishes, mid-flight
  requests included. An alias moves after the new version reports `State=Active`.

All 25 belong to three functions, and only two are handled here.

Why `wecare-seo-tools` is deliberately excluded
-----------------------------------------------
It is deployed by `scripts/deploy_seo_tools.py`, which contains no alias handling at
all. Creating a `live` alias for it and repointing its routes would mean every future
deploy updates `$LATEST`, reports success, and never reaches production - the exact
"it looked shipped" failure `ensure_plivo_dial_events_route.py` was written about.
Giving it an alias requires teaching its deployer to move one, first.

`wecare-partner-onboarding` and `wecare-marketing-ads` are both in
`deploy_all_lambdas.py`, which calls `snapstart_publish.py`, which discovers its
targets by **looking for a `live` alias** rather than from a list. So for these two
the alias starts being published and moved automatically the moment it exists.

The permission that is easy to miss
-----------------------------------
A function-level resource policy does NOT authorise an invoke of an alias. Measured
here before changing anything: `wecare-marketing-ads` has exactly one statement, on
the unqualified function. Repointing the integration to `:live` without adding an
alias-qualified statement gives API Gateway AccessDenied, which it surfaces as **500
with no Lambda log line at all**. So the permission is added before the integration
moves, and the order is not negotiable.

Usage:
    python scripts/provision_live_alias.py                 # report
    python scripts/provision_live_alias.py --apply
    python scripts/provision_live_alias.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
API_ID = "zllr9lrg7j"
ACCOUNT = "775261844268"
ALIAS = "live"

TARGETS = ("wecare-partner-onboarding", "wecare-marketing-ads")

# Excluded, with the reason, so the exclusion is not mistaken for an oversight.
EXCLUDED = {
    "wecare-seo-tools": ("deploy_seo_tools.py has no alias handling; an alias would "
                         "make every future deploy silently miss production"),
}

STATEMENT_ID = "apigw-live-alias-invoke"
SOURCE_ARN = f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}/*/*"

# Routes to probe afterwards, with the status observed BEFORE any change. A probe is
# only evidence if there is a recorded baseline to compare it against.
PROBES = (
    ("GET", "/partners/me", "401"),
    ("OPTIONS", "/marketing-ads", "200"),
)


def unqualified_arn(name: str) -> str:
    return f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{name}"


def all_items(client, operation: str):
    items = []
    for page in client.get_paginator(operation).paginate(ApiId=API_ID):
        items.extend(page.get("Items", []))
    return items


def integrations_for(api, name: str):
    """Integrations whose URI names this function WITHOUT a qualifier."""
    wanted = unqualified_arn(name)
    out = []
    for integration in all_items(api, "get_integrations"):
        uri = integration.get("IntegrationUri", "")
        # An exact match only. `...:function:foo` and `...:function:foo:live` differ by
        # the suffix, and a substring test would treat the already-correct one as
        # needing a change.
        if uri == wanted:
            out.append(integration)
    return out


def alias_version(lam, name: str):
    try:
        return lam.get_alias(FunctionName=name, Name=ALIAS)["FunctionVersion"]
    except ClientError:
        return None


def alias_has_permission(lam, name: str) -> bool:
    try:
        policy = json.loads(lam.get_policy(FunctionName=name,
                                           Qualifier=ALIAS)["Policy"])
    except ClientError:
        return False
    for statement in policy.get("Statement", []):
        arn = (statement.get("Condition", {}).get("ArnLike", {})
               .get("AWS:SourceArn", ""))
        if arn.startswith(f"arn:aws:execute-api:{REGION}:{ACCOUNT}:{API_ID}"):
            return True
    return False


def report(api, lam) -> dict:
    state = {}
    for name in TARGETS:
        integrations = integrations_for(api, name)
        state[name] = {
            "alias": alias_version(lam, name),
            "aliasPermission": alias_has_permission(lam, name),
            "unqualifiedIntegrations": [i["IntegrationId"] for i in integrations],
            "target": None,
        }
        print(f"{name}")
        print(f"  {ALIAS} alias: {state[name]['alias'] or 'MISSING'}")
        print(f"  alias invoke permission: "
              f"{'present' if state[name]['aliasPermission'] else 'MISSING'}")
        print(f"  integrations still on $LATEST: "
              f"{len(state[name]['unqualifiedIntegrations'])}")
    for name, reason in EXCLUDED.items():
        print(f"{name}\n  EXCLUDED: {reason}")
    return state


def route_count_for(api, integration_ids) -> int:
    ids = {f"integrations/{i}" for i in integration_ids}
    return sum(1 for r in all_items(api, "get_routes") if r.get("Target") in ids)


def apply(api, lam, state) -> int:
    for name, info in state.items():
        print(f"\n{name}")

        version = info["alias"]
        if version is None:
            published = lam.publish_version(FunctionName=name)
            version = published["Version"]
            # A version is not invocable until it is Active. Pointing an alias at a
            # Pending version is how a cutover produces a cold 500.
            for _ in range(30):
                conf = lam.get_function_configuration(
                    FunctionName=name, Qualifier=version)
                if conf.get("State") == "Active":
                    break
                time.sleep(2)
            else:
                print(f"  v{version} never reached Active; stopping",
                      file=sys.stderr)
                return 2
            lam.create_alias(FunctionName=name, Name=ALIAS,
                             FunctionVersion=version,
                             Description="Production traffic; moved by "
                                         "snapstart_publish.py")
            print(f"  published v{version}, created {ALIAS} -> v{version}")
        else:
            print(f"  {ALIAS} already -> v{version}")

        # BEFORE the integration moves. A function-level statement does not cover an
        # alias invoke, and the failure mode is a 500 with no log line.
        if not info["aliasPermission"]:
            try:
                lam.add_permission(
                    FunctionName=name, Qualifier=ALIAS,
                    StatementId=STATEMENT_ID, Action="lambda:InvokeFunction",
                    Principal="apigateway.amazonaws.com", SourceArn=SOURCE_ARN)
                print(f"  added {STATEMENT_ID} on alias {ALIAS}")
            except lam.exceptions.ResourceConflictException:
                print(f"  {STATEMENT_ID} already present")
        else:
            print("  alias invoke permission already present")

        qualified = f"{unqualified_arn(name)}:{ALIAS}"
        for integration_id in info["unqualifiedIntegrations"]:
            api.update_integration(ApiId=API_ID, IntegrationId=integration_id,
                                   IntegrationUri=qualified)
            print(f"  integration {integration_id} -> :{ALIAS}")

    return 0


def probe(method: str, path: str) -> str:
    request = urllib.request.Request(
        f"https://api.wecare.digital{path}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return str(response.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__


def verify() -> int:
    problems = []
    api = boto3.client("apigatewayv2", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    state = report(api, lam)

    for name, info in state.items():
        if info["alias"] is None:
            problems.append(f"{name} has no {ALIAS} alias")
        if not info["aliasPermission"]:
            problems.append(f"{name} alias cannot be invoked by API Gateway; its "
                            f"routes will return 500")
        if info["unqualifiedIntegrations"]:
            problems.append(f"{name} still has "
                            f"{len(info['unqualifiedIntegrations'])} integration(s) "
                            f"on $LATEST")

    print("\nprobes (compared against the status recorded before the change):")
    for method, path, expected in PROBES:
        got = probe(method, path)
        verdict = "same" if got == expected else f"CHANGED from {expected}"
        print(f"  {method} {path} -> {got} ({verdict})")
        if got == "500":
            problems.append(f"{method} {path} returned 500; the alias invoke "
                            f"permission is missing and the Lambda was never called")
        elif got != expected:
            problems.append(f"{method} {path} was {expected} before and is {got} now")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nboth functions behind {ALIAS}; no route changed its response")
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
        print(f"could not read the account: {type(exc).__name__}", file=sys.stderr)
        return 2

    done = all(info["alias"] and info["aliasPermission"]
               and not info["unqualifiedIntegrations"]
               for info in state.values())
    if done:
        print("\nnothing to do; run --verify to probe")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1

    rc = apply(api, lam, state)
    if rc:
        return rc
    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
