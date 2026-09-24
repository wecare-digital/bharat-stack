#!/usr/bin/env python3
"""Create and associate the two web ACLs this account can actually have.

The constraint that shapes everything below
-------------------------------------------
**AWS WAF cannot protect an HTTP API.** Its protected resource types are a CloudFront
distribution, an API Gateway **REST** API, an Application Load Balancer, an AppSync
GraphQL API, an Amazon Cognito user pool, an App Runner service, an Amplify
application, and a Verified Access instance. `zllr9lrg7j` is an HTTP API
(apigatewayv2), so no web ACL can ever be attached to it. That is a service limit, not
a decision, and the owner override's "WAF must be implemented and live-verified" has to
be met on the surfaces that support it:

| Surface | Scope | Why it is worth protecting |
|---|---|---|
| Amplify app `d22dm4b0jn71jw` | `CLOUDFRONT` | the dashboard and the public site |
| Cognito pool `us-east-1_cSx0RHCIR` | `REGIONAL` | managed login + the pool's API endpoints |

Two web ACLs, because the scopes are incompatible: Amplify requires a CloudFront-scope
ACL created in us-east-1, and a regional ACL is explicitly not usable with Amplify.

The API's own protection is unchanged and is not WAF's job here: handler-level
`require_auth`, provider signature verification on webhooks, and per-route Lambda
invoke permissions.

Why the two ACLs are configured differently
-------------------------------------------
This is the part that would be wrong if it were uniform.

**Amplify: blocking.** The app serves a static Next.js export - GETs for HTML, JS and
images, no form posts, no request bodies worth inspecting. The AWS managed rule groups
have essentially no legitimate traffic to false-positive on, so they run in BLOCK. Real
enforcement, and cheap to undo: one `disassociate_web_acl` call.

**Cognito: rate limiting blocks, managed rules count.** The actual threat to a sign-in
endpoint is credential stuffing, which a rate-based rule answers directly. Putting the
Core rule set in BLOCK in front of managed login without tuning risks refusing a
legitimate sign-in - and the only account in this pool belongs to the person who would
then be unable to get in to fix it. AWS's own guidance for Cognito is to test and tune
before enforcing. So the managed groups are in COUNT, deliberately and temporarily.

**COUNT is only honest if somebody can read the counts**, which is why logging is part
of this script rather than a follow-up. A rule set counting into nothing is the audit
sink that failed open in a new costume. Both ACLs log to `aws-waf-logs-*` groups with
the house 30-day retention.

Live verification, and why one surface can be proven and the other cannot
------------------------------------------------------------------------
For Amplify the proof is a real blocked request: a Log4Shell probe string
(`${jndi:ldap://...}`) in a query parameter is matched by
`AWSManagedRulesKnownBadInputsRuleSet`. Sending one and getting **403** proves the web
ACL is inspecting live traffic and enforcing. It is completely inert - the string is
matched and dropped, and nothing in this stack interprets JNDI.

For Cognito there is no safe equivalent. The only BLOCK rule is rate-based, and
tripping it means sending thousands of requests at our own sign-in endpoint, which is a
denial of service against ourselves. So Cognito is verified by association plus
`AWS/WAFV2` CloudWatch metrics recording inspected requests - the association is
provable, the blocking is not exercised, and this script says so rather than implying
otherwise.

Cost, stated because it is a recurring charge
---------------------------------------------
WAF bills roughly $5/month per web ACL plus $1/month per rule, plus per-request
charges. Two ACLs with the rules below is on the order of $17/month before request
volume. Amplify's WAF integration may add a per-app fee.

Usage:
    python scripts/provision_waf.py            # report
    python scripts/provision_waf.py --apply
    python scripts/provision_waf.py --verify
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
ACCOUNT = "775261844268"

AMPLIFY_APP_ID = "d22dm4b0jn71jw"
AMPLIFY_APP_ARN = f"arn:aws:amplify:{REGION}:{ACCOUNT}:apps/{AMPLIFY_APP_ID}"
USER_POOL_ID = "us-east-1_cSx0RHCIR"
USER_POOL_ARN = f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/{USER_POOL_ID}"

AMPLIFY_ACL = "wecare-amplify-waf"
COGNITO_ACL = "wecare-cognito-waf"

AMPLIFY_LOG_GROUP = "aws-waf-logs-wecare-amplify"
COGNITO_LOG_GROUP = "aws-waf-logs-wecare-cognito"
LOG_RETENTION_DAYS = 30

SITE = "https://wecare.digital"
# Matched by AWSManagedRulesKnownBadInputsRuleSet. Inert: nothing here interprets JNDI,
# and the point is that the request never reaches the origin at all.
PROBE_PAYLOAD = "${jndi:ldap://waf-selftest.invalid/a}"


def managed(name: str, priority: int, *, count: bool):
    """An AWS managed rule group, in BLOCK or COUNT.

    `overrideAction: {count: {}}` counts every rule in the group without blocking.
    `{none: {}}` lets each rule's own action stand, which for these groups is block.
    """
    return {
        "Name": name,
        "Priority": priority,
        "Statement": {
            "ManagedRuleGroupStatement": {"VendorName": "AWS", "Name": name}},
        "OverrideAction": {"Count": {}} if count else {"None": {}},
        "VisibilityConfig": {
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": name,
        },
    }


def rate_rule(name: str, priority: int, limit: int):
    return {
        "Name": name,
        "Priority": priority,
        "Statement": {
            "RateBasedStatement": {"Limit": limit, "AggregateKeyType": "IP"}},
        "Action": {"Block": {}},
        "VisibilityConfig": {
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": name,
        },
    }


# Amplify: real enforcement. A static export gives the managed groups nothing
# legitimate to trip on.
AMPLIFY_RULES = [
    rate_rule("rate-limit-per-ip", 0, 2000),
    managed("AWSManagedRulesAmazonIpReputationList", 1, count=False),
    managed("AWSManagedRulesKnownBadInputsRuleSet", 2, count=False),
    managed("AWSManagedRulesCommonRuleSet", 3, count=False),
]

# Cognito: the rate rule blocks; the managed groups observe. Blocking an untuned Core
# rule set in front of managed login could refuse the only account in this pool.
COGNITO_RULES = [
    rate_rule("auth-rate-limit-per-ip", 0, 1000),
    managed("AWSManagedRulesAmazonIpReputationList", 1, count=True),
    managed("AWSManagedRulesCommonRuleSet", 2, count=True),
]

PLAN = {
    AMPLIFY_ACL: {
        "scope": "CLOUDFRONT",
        "rules": AMPLIFY_RULES,
        "resource": AMPLIFY_APP_ARN,
        "logGroup": AMPLIFY_LOG_GROUP,
        "description": "Blocking web ACL for the Amplify-hosted dashboard and site",
    },
    COGNITO_ACL: {
        "scope": "REGIONAL",
        "rules": COGNITO_RULES,
        "resource": USER_POOL_ARN,
        "logGroup": COGNITO_LOG_GROUP,
        # WAF restricts this field to [\w+=:#@/\-,\.] plus spaces - no semicolons,
        # no parentheses. The first attempt was rejected for a semicolon.
        "description": ("Rate limiting blocks. Managed rule groups count until tuned, "
                        "because an untuned block on managed login could refuse the "
                        "only account in the pool"),
    },
}


def waf():
    # CloudFront-scope calls must go to us-east-1; regional ones may as well.
    return boto3.client("wafv2", region_name=REGION)


def find_acl(client, name: str, scope: str):
    token = None
    while True:
        kw = {"Scope": scope, "Limit": 100}
        if token:
            kw["NextMarker"] = token
        page = client.list_web_acls(**kw)
        for acl in page.get("WebACLs", []):
            if acl["Name"] == name:
                return acl
        token = page.get("NextMarker")
        if not token or not page.get("WebACLs"):
            return None


def ensure_log_group(name: str) -> None:
    logs = boto3.client("logs", region_name=REGION)
    try:
        logs.create_log_group(logGroupName=name)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    logs.put_retention_policy(logGroupName=name,
                              retentionInDays=LOG_RETENTION_DAYS)


def logging_enabled(client, acl_arn: str) -> bool:
    try:
        client.get_logging_configuration(ResourceArn=acl_arn)
        return True
    except ClientError:
        return False


def associated_acl_arn(client, resource_arn: str, scope: str) -> str:
    """The web ACL protecting this resource, or ''.

    `get_web_acl_for_resource` is the only honest answer here: an ACL can exist and
    protect nothing, which is the state this script was written to leave behind never
    again.
    """
    try:
        got = client.get_web_acl_for_resource(ResourceArn=resource_arn)
    except ClientError:
        return ""
    return (got.get("WebACL") or {}).get("ARN", "")


def report(client) -> dict:
    state = {}
    for name, spec in PLAN.items():
        acl = find_acl(client, name, spec["scope"])
        arn = acl["ARN"] if acl else ""
        state[name] = {
            "arn": arn,
            "id": acl["Id"] if acl else "",
            "lockToken": acl["LockToken"] if acl else "",
            "logging": logging_enabled(client, arn) if arn else False,
            "protecting": associated_acl_arn(client, spec["resource"],
                                             spec["scope"]) == arn and bool(arn),
        }
        blocking = [r["Name"] for r in spec["rules"]
                    if r.get("Action", {}).get("Block") is not None
                    or r.get("OverrideAction", {}).get("None") is not None]
        counting = [r["Name"] for r in spec["rules"]
                    if r.get("OverrideAction", {}).get("Count") is not None]
        print(f"{name} ({spec['scope']})")
        print(f"  web ACL: {'present' if arn else 'MISSING'}")
        print(f"  associated with {spec['resource'].split('/')[-1]}: "
              f"{'yes' if state[name]['protecting'] else 'NO'}")
        print(f"  logging: {'on' if state[name]['logging'] else 'OFF'}")
        print(f"  blocking rules: {blocking}")
        print(f"  counting rules: {counting or '[]'}")
    return state


def apply(client, state) -> int:
    for name, spec in PLAN.items():
        info = state[name]
        print(f"\n{name}")

        if not info["arn"]:
            created = client.create_web_acl(
                Name=name, Scope=spec["scope"],
                DefaultAction={"Allow": {}},
                Description=spec["description"],
                Rules=spec["rules"],
                VisibilityConfig={
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
                Tags=[{"Key": "Project", "Value": "WECARE.DIGITAL"}],
            )
            info["arn"] = created["Summary"]["ARN"]
            print(f"  created web ACL {info['arn'].split('/')[-1]}")
            # Propagation: a CloudFront-scope ACL is not immediately associable.
            time.sleep(8)
        else:
            print("  web ACL already exists")

        if not info["logging"]:
            ensure_log_group(spec["logGroup"])
            log_arn = (f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:"
                       f"{spec['logGroup']}")
            try:
                client.put_logging_configuration(
                    LoggingConfiguration={
                        "ResourceArn": info["arn"],
                        "LogDestinationConfigs": [log_arn],
                    })
                print(f"  logging -> {spec['logGroup']} "
                      f"({LOG_RETENTION_DAYS}d retention)")
            except ClientError as exc:
                print(f"  logging FAILED: "
                      f"{exc.response.get('Error', {}).get('Code')}",
                      file=sys.stderr)
        else:
            print("  logging already configured")

        if not info["protecting"]:
            # A freshly created web ACL is not immediately associable and WAF answers
            # `WAFUnavailableEntityException` while it propagates. Observed on the
            # regional ACL with an 8 second wait, so this retries rather than treating
            # a transient as a failure - a script that gives up here leaves an ACL that
            # exists and protects nothing, which is the worst of the three states.
            for attempt in range(10):
                try:
                    client.associate_web_acl(WebACLArn=info["arn"],
                                             ResourceArn=spec["resource"])
                    print(f"  associated with {spec['resource'].split('/')[-1]}")
                    break
                except ClientError as exc:
                    code = exc.response.get("Error", {}).get("Code")
                    if code == "WAFUnavailableEntityException" and attempt < 9:
                        time.sleep(10)
                        continue
                    print(f"  association FAILED: {code}", file=sys.stderr)
                    return 2
        else:
            print("  already associated")
    return 0


def probe(path: str, query: str = "") -> str:
    url = f"{SITE}{path}"
    if query:
        url += "?" + urllib.parse.urlencode({"q": query})
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, method="GET"), timeout=20) as response:
            return str(response.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__


def verify() -> int:
    problems = []
    client = waf()
    state = report(client)

    for name, spec in PLAN.items():
        info = state[name]
        if not info["arn"]:
            problems.append(f"{name} does not exist")
            continue
        if not info["protecting"]:
            problems.append(f"{name} exists but protects nothing - "
                            f"{spec['resource']} has no web ACL")
        if not info["logging"]:
            problems.append(f"{name} has no logging, so its COUNT rules record "
                            f"into nothing anybody reads")

    print("\nlive enforcement check on the Amplify surface:")
    baseline = probe("/")
    blocked = probe("/", PROBE_PAYLOAD)
    print(f"  GET / -> {baseline}")
    print(f"  GET / with a Log4Shell probe in the query -> {blocked}")
    if baseline != "200":
        problems.append(f"the site itself returned {baseline}; the web ACL may be "
                        f"blocking legitimate traffic")
    if blocked != "403":
        problems.append(
            f"a known-bad-input probe returned {blocked}, expected 403. The web ACL "
            f"is not enforcing on live traffic (CloudFront-scope propagation can take "
            f"several minutes - re-run --verify before concluding it is broken)")

    print("\nnot verified, and stated rather than implied:")
    print("  - the Cognito rate-based rule is NOT exercised. Tripping it means "
          "thousands of requests at our own sign-in endpoint.")
    print("  - the Cognito managed rule groups are in COUNT, so they block nothing "
          "yet. Read the logs, then flip them.")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nboth web ACLs exist, are associated, and log; Amplify enforcement proven "
          "by a blocked request")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    if args.verify:
        return verify()

    client = waf()
    try:
        state = report(client)
    except (ClientError, BotoCoreError) as exc:
        print(f"could not read WAF: {type(exc).__name__}", file=sys.stderr)
        return 2

    done = all(i["arn"] and i["protecting"] and i["logging"] for i in state.values())
    if done:
        print("\nnothing to do; run --verify to probe")
        return 0
    if not args.apply:
        print("\nre-run with --apply to converge")
        return 1

    rc = apply(client, state)
    if rc:
        return rc
    print("\nwaiting for CloudFront-scope propagation before verifying...")
    time.sleep(45)
    print("\nread-back verification:")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
