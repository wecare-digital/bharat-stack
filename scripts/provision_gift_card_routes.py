#!/usr/bin/env python3
"""Provision the gift-card HTTP API routes: three SPI paths and five of our own.

Design reference: `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
sections 7.1 (the SPI routes), 7.2 (our own routes) and 5.2 (why the SPI route carries no
authorizer).

NAMED `provision_gift_card_routes.py`, NOT `..._spi_routes.py` (NIT-3)
---------------------------------------------------------------------
It creates EIGHT routes across TWO functions, and only three of them are SPI. A file named
`..._spi_routes.py` that also creates five non-SPI routes misleads the next reader about what it
touches, which matters because one of the two integrations is internet-facing with no authorizer and
the other is not.

| | |
|---|---|
| API | HTTP API `zllr9lrg7j`, the account's only one |
| Stage | `prod`. There is no `$default` stage, so the raw execute-api host needs the `/prod` segment |
| Integrations | TWO `AWS_PROXY` payload-2.0 integrations, one per function, each onto `:live` |
| Permission | one `lambda:InvokeFunction` statement per route, `SourceArn` scoped to its own path family |
| Idempotence | an existing route is reported, never recreated or retargeted |

THE SPI's `deploymentUri`
-------------------------
Wix is registered with the base URI

    https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/wix-giftcards/

and appends `v1/balance`, `v1/redeem`, `v1/void`. The account has no API Gateway custom domain, and
the apex `wecare.digital/api/*` path is an Amplify-side rewrite serving browsers rather than a
server-to-server front door - routing Wix's signed, non-idempotent calls through a CDN we do not
control would add a hop and a cache layer in front of a payment endpoint. The cost is recorded: a
later move to a custom domain means RE-REGISTERING with Wix, not editing a route.

THE INTEGRATIONS TARGET THE ALIAS, NOT `$LATEST`
------------------------------------------------
`lambda-snapstart-deploy.md`: 58 of 65 functions are invoked through their `live` alias, and a
`$LATEST` change does not reach production until a version is published and the alias moves. An
integration pointed at `$LATEST` would serve whatever was last uploaded, which is the opposite of
that control. The invoke permission is QUALIFIED to the alias for the same reason - a
function-level statement does not authorise an alias invoke, and the failure mode is a 500 with no
Lambda log line at all, because the function is never entered.

AUTHORIZATION
-------------
All eight routes are created with `AuthorizationType=NONE` and no authorizer, because this account
has zero API Gateway authorizers across 361 routes and this change does not introduce the first one.
For the five own routes, authentication is `middleware.require_auth` on the four staff routes and a
customer-session check on `POST /gift-cards/balance`, inside the handler. For the three SPI routes
there can BE no gateway authorizer: Wix presents its own JWT, not a Cognito token, and verification
is the first thing that handler does - before the body is interpreted and before any table access.

`00-current-owner-overrides.md` records why the gateway field cannot be read as the answer either
way: it cannot distinguish an intentionally public signed webhook from an accidentally public API.
With WAF removed by owner decision, handler-level verification plus `lambda_utils/rate_limit.py` plus
stage/route throttling is the whole filter in front of these routes.

ADDITIVE ONLY
-------------
361 pre-existing routes belong to other functions. This script never calls `delete_route`,
`delete_integration`, `update_route` or `update_integration`.

Usage:
    python scripts/provision_gift_card_routes.py              # dry run, the default
    python scripts/provision_gift_card_routes.py --apply
    python scripts/provision_gift_card_routes.py --verify
"""

from __future__ import annotations

import argparse
import json

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
ACCOUNT_ID = "775261844268"

#: The account's single HTTP API ("wecare-digital-api") and its only stage, which auto-deploys.
API_ID = "zllr9lrg7j"
STAGE = "prod"
LIVE_ALIAS = "live"

GIFT_CARDS_FUNCTION = "wecare-gift-cards"
SPI_FUNCTION = "wecare-wix-giftcard-spi"

#: FIVE routes, not seven. `POST /gift-cards/hold` and `POST /gift-cards/release` are deliberately
#: absent (MEDIUM-5): a customer session has no `paymentAttemptId`, and a hold taken outside the
#: request that mints one skips the `GC_HELD` stage - leaving `giftCardRequiredPaise` unwritten, so
#: `is_fully_settled` reads `required == 0` and would settle a gift-card order on the Razorpay leg
#: alone. The hold is taken only by the checkout producer.
#:
#: No route takes a CODE in a path or a query: a bearer value in a URL lands in access logs, in
#: `Referer` headers and in browser history. The staff reads take our own `giftCardId`; the customer
#: route takes `{code, pin?}` in the BODY. There is no `DELETE` - a disabled card retains its
#: liability record.
OWN_ROUTE_KEYS = (
    "POST /gift-cards",
    "GET /gift-cards/{giftCardId}",
    "GET /gift-cards",
    "POST /gift-cards/{giftCardId}/disable",
    "POST /gift-cards/balance",
)

#: Exactly the three documented SPI methods. Deliberately NOT a `{proxy+}`: the surface stays as wide
#: as the design and no wider, so a fourth path cannot appear without a design change.
SPI_ROUTE_KEYS = (
    "POST /wix-giftcards/v1/balance",
    "POST /wix-giftcards/v1/redeem",
    "POST /wix-giftcards/v1/void",
)

#: function -> (its route keys, the source-ARN path family). Narrower than `{API_ID}/*/*`, which
#: would authorise any method on any of the 361 routes.
PLAN = (
    (GIFT_CARDS_FUNCTION, OWN_ROUTE_KEYS, "gift-cards*", "Gift-card issuance and balance"),
    (SPI_FUNCTION, SPI_ROUTE_KEYS, "wix-giftcards*", "Wix Gift Cards Service Plugin"),
)

SOURCE_ARN_PREFIX = f"arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:{API_ID}"


def api():
    return boto3.client("apigatewayv2", region_name=REGION)


def lam():
    return boto3.client("lambda", region_name=REGION)


def function_arn(function: str, *, qualified: bool = True) -> str:
    arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{function}"
    return f"{arn}:{LIVE_ALIAS}" if qualified else arn


def source_arn(family: str) -> str:
    """The source ARN for one path family.

    A family rather than a per-route literal, because a templated route key (`{giftCardId}`) is
    presented by API Gateway with the resolved value substituted - so a literal would not match the
    request it is meant to authorise.
    """
    return f"{SOURCE_ARN_PREFIX}/*/*/{family}"


def route_statement_id(function: str, route_key: str) -> str:
    method, path = route_key.split(" ", 1)
    slug = path.strip("/").replace("/", "-").replace("{", "").replace("}", "")
    return f"apigw-{function}-{method.lower()}-{slug}"


def _all_items(method: str) -> list:
    client = api()
    paginate, items, token = getattr(client, method), [], None
    while True:
        kwargs = {"ApiId": API_ID, "MaxResults": "1000"}
        if token:
            kwargs["NextToken"] = token
        page = paginate(**kwargs)
        items.extend(page.get("Items", []))
        token = page.get("NextToken")
        if not token:
            return items


def find_integration(uri: str) -> str:
    for integration in _all_items("get_integrations"):
        if integration.get("IntegrationUri") == uri:
            return integration["IntegrationId"]
    return ""


def ensure_integration(function: str, description: str, apply: bool) -> tuple:
    """Reuse-or-create ONE `AWS_PROXY` integration per function, pointing at the alias."""
    uri = function_arn(function)
    existing = find_integration(uri)
    if existing:
        return existing, f"reusing {existing}"
    if not apply:
        return "", f"would create AWS_PROXY -> {uri}"
    created = api().create_integration(
        ApiId=API_ID, IntegrationType="AWS_PROXY", IntegrationUri=uri,
        PayloadFormatVersion="2.0", Description=description)
    return created["IntegrationId"], f"created {created['IntegrationId']} -> {uri}"


def ensure_routes(route_keys, integration_id: str, apply: bool) -> str:
    """Create only missing route keys. Never deletes or retargets an existing route."""
    existing = {r["RouteKey"]: r["RouteId"] for r in _all_items("get_routes")}
    results = []
    for key in route_keys:
        if key in existing:
            results.append(f"{key} exists ({existing[key]})")
            continue
        if not apply:
            results.append(f"would create {key}")
            continue
        made = api().create_route(ApiId=API_ID, RouteKey=key,
                                  Target=f"integrations/{integration_id}")
        results.append(f"created {key} ({made['RouteId']})")
    return "; ".join(results)


def live_policy_statements(function: str) -> list:
    """The alias's resource-policy statements, or an empty list when it has none yet."""
    try:
        policy = lam().get_policy(FunctionName=function, Qualifier=LIVE_ALIAS)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("ResourceNotFoundException",
                                                         "ResourceNotFound"):
            return []
        raise
    return json.loads(policy.get("Policy") or "{}").get("Statement") or []


def _statement_source_arn(statement: dict) -> str:
    return (((statement.get("Condition") or {}).get("ArnLike") or {})
            .get("AWS:SourceArn") or "")


def ensure_invoke_permission(function: str, route_keys, family: str, apply: bool) -> str:
    """One alias-qualified `lambda:InvokeFunction` statement per route.

    Qualified to `live`, because a function-level statement does not authorise an alias invoke.
    Statements are OR'd, so adding one can never remove authorisation from an existing route.
    """
    existing = {s.get("Sid"): s for s in live_policy_statements(function)}
    notes = []
    for key in route_keys:
        sid = route_statement_id(function, key)
        if sid in existing:
            notes.append(f"{sid} exists ({_statement_source_arn(existing[sid])})")
            continue
        if not apply:
            notes.append(f"would add {sid} -> {source_arn(family)}")
            continue
        lam().add_permission(
            FunctionName=function, Qualifier=LIVE_ALIAS, StatementId=sid,
            Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
            SourceArn=source_arn(family))
        notes.append(f"added {sid}")
    return "; ".join(notes)


def verify() -> int:
    """Read routes, integrations and every invoke statement back. Non-zero on any problem."""
    problems: list[str] = []
    integrations = {i["IntegrationId"]: i for i in _all_items("get_integrations")}
    routes = {r["RouteKey"]: r for r in _all_items("get_routes")}

    for function, route_keys, family, _description in PLAN:
        uri = function_arn(function)
        integration_id = find_integration(uri)
        if not integration_id:
            problems.append(f"no AWS_PROXY integration targets {uri}")
        else:
            integration = integrations[integration_id]
            if integration.get("PayloadFormatVersion") != "2.0":
                problems.append(f"{function}: payload format is "
                                f"{integration.get('PayloadFormatVersion')}, expected 2.0")
            if integration.get("IntegrationType") != "AWS_PROXY":
                problems.append(f"{function}: integration type is "
                                f"{integration.get('IntegrationType')}")
            if not str(integration.get("IntegrationUri") or "").endswith(f":{LIVE_ALIAS}"):
                problems.append(f"{function}: the integration does not target the live alias")

        for key in route_keys:
            route = routes.get(key)
            if not route:
                problems.append(f"missing route {key}")
                continue
            if integration_id and route.get("Target") != f"integrations/{integration_id}":
                problems.append(f"route {key} targets {route.get('Target')}, not {function}'s "
                                f"integration")
            if route.get("AuthorizerId"):
                problems.append(f"route {key} carries an authorizer this script did not create")
            # No code may appear in a route template.
            if "{code}" in key or "code=" in key:
                problems.append(f"route {key} carries a code in its path")

        statements = {s.get("Sid"): s for s in live_policy_statements(function)}
        for key in route_keys:
            sid = route_statement_id(function, key)
            if sid not in statements:
                problems.append(f"missing invoke statement {sid}")
                continue
            arn = _statement_source_arn(statements[sid])
            if arn != source_arn(family):
                problems.append(f"{sid} is scoped to {arn}, expected {source_arn(family)}")
        unexpected = sorted(set(statements)
                            - {route_statement_id(function, k) for k in route_keys})
        if unexpected:
            problems.append(f"unexpected invoke statements on {function}:{LIVE_ALIAS}: "
                            f"{unexpected}")

        print(f"function: {function}")
        print(f"  integration: {integration_id or 'MISSING'} -> {uri}")
        for key in route_keys:
            print(f"  route {key}: {'ok' if key in routes else 'MISSING'}")
        print(f"  invoke statements: {sorted(statements)}")

    # The two hold/release routes must NOT exist (MEDIUM-5). Asserted rather than assumed, because
    # a route created by hand would be reachable and unprovisioned.
    for forbidden in ("POST /gift-cards/hold", "POST /gift-cards/release"):
        if forbidden in routes:
            problems.append(f"{forbidden} exists; a customer-taken hold skips the GC_HELD stage "
                            f"and would settle a gift-card order on the Razorpay leg alone")

    print(f"api: {API_ID} stage {STAGE}")
    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\ngift-card routes verified")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="create what is missing; without it this is a dry run")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    print(f"region: {REGION}\napply: {args.apply}\n")
    for function, route_keys, family, description in PLAN:
        integration_id, note = ensure_integration(function, description, args.apply)
        print(f"{function} integration: {note}")
        # The permission goes on BEFORE the routes, so a route is never reachable-but-unauthorised.
        print(f"{function} permissions: "
              f"{ensure_invoke_permission(function, route_keys, family, args.apply)}")
        print(f"{function} routes: {ensure_routes(route_keys, integration_id, args.apply)}")
    if not args.apply:
        print("\ndry run: nothing changed")
        return 0
    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
